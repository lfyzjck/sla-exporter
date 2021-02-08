import logging
import subprocess
import socket
import os
import time

import requests
from schematics.models import Model
from schematics.types import (
    BooleanType,
    DictType,
    IntType,
    ListType,
    ModelType,
    StringType,
)
from sla_exporter.module_utils import register_module
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import URL


MODULE_CLS = {}

logger = logging.getLogger(__name__)


class HTTPParams(Model):
    method = StringType(choices=["GET", "POST", "PUT"], default="GET")
    body = StringType(default=None)
    headers = DictType(StringType, default=dict)


class BaseModule(Model):
    prober = StringType(choices=["http", "shell", "tcp"])

    def check(self, service_name: str, target: str) -> bool:
        raise NotImplementedError()


@register_module(MODULE_CLS, "http_2xx")
class HTTPModule(BaseModule):
    http = ModelType(HTTPParams, default=lambda: HTTPParams())
    valid_status_codes = ListType(IntType, default=lambda: [200, 201, 204])
    timeout = IntType(default=10)
    no_follow_redirects = BooleanType(default=False)

    def check(self, service_name: str, target_url: str) -> bool:
        is_success = False
        try:
            resp = requests.request(
                method=self.http.method,
                url=target_url,
                data=self.http.body,
                headers=self.http.headers,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            is_success = True
        except Exception:
            logger.exception(
                f"request failed. url: {target_url}, timeout: {self.timeout}"
            )
        return is_success


@register_module(MODULE_CLS, "script")
class ScriptModule(BaseModule):
    valid_exit_codes = ListType(IntType, default=lambda: [0])
    timeout = IntType(default=60)

    def check(self, service_name: str, target: str) -> bool:
        is_success = False
        try:
            logger.info(f"execute script {service_name}: {target}")
            subprocess.run(
                target, timeout=self.timeout, check=True, shell=True, env=os.environ
            )
            # 命令执行成功
            is_success = True
        except Exception:
            logger.exception(f"command {target} execute with errors: ")
        return is_success


@register_module(MODULE_CLS, "tcp")
class TCPModule(BaseModule):

    # socket connect timeout(seconds)
    timeout = IntType(default=5)

    def check(self, service_name: str, target: str) -> bool:
        host, port = target.split(":")
        is_success = False
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((host, int(port)))
                is_success = True
        except Exception as e:
            logger.exception("tcp target connect failed with error", e)
        return is_success


@register_module(MODULE_CLS, "sqlalchemy")
class SQLAlchemyModule(BaseModule):
    driver = StringType(required=True, choices=("mysql",))
    host = StringType(required=True)
    port = IntType(required=True)
    user = StringType(required=True)
    password = StringType(required=False, default=None)
    database = StringType(required=False, default="")
    connect_args = DictType(StringType, default=dict)

    def get_connect_uri(self):
        return URL(
            self.driver,
            self.user,
            self.password,
            host=self.host,
            port=self.port,
            database=self.database,
        )

    def check(self, service_name: str, target: str) -> bool:
        is_success = False
        connect_args = self.connect_args
        connect_uri = self.get_connect_uri()
        logger.info(f"connect to {connect_uri}")
        engine = create_engine(connect_uri, connect_args=connect_args)
        try:
            with engine.connect() as conn:
                logger.info(f"execute statement: {target}, uri: {connect_uri}")
                conn.execute(text(target))
                is_success = True
        except Exception:
            logger.exception("query {self.driver} failed")
        return is_success


@register_module(MODULE_CLS, "doris")
class DorisModule(SQLAlchemyModule):
    driver = StringType(required=False, choices=("mysql",), default="mysql")
    charset = StringType(required=False, default="utf8")
    # mysql_native_password 是 mysql 较早的认证方式，这里配置是为了兼容 Doris 的认证协议
    connect_args = DictType(
        StringType, default=lambda: {"auth_plugin": "mysql_native_password"}
    )

    def check(self, service_name: str, target: str):
        connect_args = self.connect_args
        hosts = self.host.split(",")
        is_success = False
        # 尝试多个 host
        for i, host in enumerate(hosts):
            connect_uri = URL(
                self.driver,
                self.user,
                self.password,
                host=host,
                port=self.port,
                database=self.database,
                query={"charset": self.charset},
            )
            logger.info(f"connect to {connect_uri}")
            engine = create_engine(connect_uri, connect_args=connect_args)
            try:
                with engine.connect() as conn:
                    logger.info(
                        f"execute statement: {target}, uri: {connect_uri}, times: {i}"
                    )
                    conn.execute(text(target))
                    is_success = True
                    # 有 1 次成功结束循环
                    break
            except Exception:
                logger.exception("query doris failed")
        return is_success


@register_module(MODULE_CLS, "presto")
class PrestoModule(SQLAlchemyModule):
    driver = StringType(required=False, default="presto")
