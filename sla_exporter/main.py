#!/usr/bin/env python3
import argparse
import logging
import logging.config
import os
from functools import partial
from pathlib import PurePath
from time import time

import yaml
from apscheduler.executors.twisted import TwistedExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.twisted import TwistedScheduler
from prometheus_client.twisted import MetricsResource
from schematics.exceptions import ConversionError
from schematics.models import Model
from schematics.types import CompoundType, IntType, ListType, StringType
from twisted.internet import reactor
from twisted.web.resource import Resource
from twisted.web.server import Site
from prometheus_client import Counter, Gauge

from sla_exporter.modules import MODULE_CLS
from sla_exporter.utils import expand_patterns, is_parttern

logger = logging.getLogger(__name__)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[%(levelname)s][%(name)s] %(asctime)s %(message)s"},
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "loggers": {
        "": {
            "level": "INFO",
            "handlers": ["console"],
        },
    },
}
logging.config.dictConfig(LOGGING)
BASE_DIR = PurePath(os.path.abspath(__file__)).parent
CONFIG_DIR = os.path.join(BASE_DIR, "config")
SERVICES = []
LABELS = ["group", "target"]

metric_request = Gauge("sla_request_success", "", LABELS)
metric_request_count = Counter("sla_request_count", "", LABELS)
metric_duration = Gauge("sla_request_duration", "", LABELS)


class DynamicDictType(CompoundType):
    def _convert(self, value, context):
        if isinstance(value, dict):
            return value
        else:
            raise ConversionError("Input must be a dict")

    def _export(self, value, format, context):
        return value


class Service(Model):
    name = StringType(max_length=255)
    project = StringType(required=False, default=None)
    module = StringType(max_length=32)
    module_config = DynamicDictType(required=False, default=dict)
    interval = IntType(default=60)
    targets = ListType(StringType)


def create_module_instance(module, module_config):
    module_cls = MODULE_CLS[module]
    return module_cls(module_config)


def load_services(config):
    with open(config) as f:
        data = yaml.safe_load(f)
        for service in data["services"]:
            service_model = Service(service)
            service_model.validate()
            SERVICES.append(service_model)


def build_labels(labels):
    return [labels.get(name, "default") for name in LABELS]


def run_check(service: Service, target: str):
    """
    执行 check 操作
    """
    module = create_module_instance(service.module, service.module_config)
    labels = build_labels(
        {
            "group": service.name,
            "target": target,
        }
    )
    metric_request_count.labels(*labels).inc()
    start_time = time()
    is_success = module.check(service.name, target)
    end_time = time()
    metric_duration.labels(*labels).set(end_time - start_time)
    metric_request.labels(*labels).set(int(is_success))


def create_scheduler(reactor):
    jobstores = {"default": MemoryJobStore()}
    executors = {"default": TwistedExecutor()}
    job_defaults = {"coalesce": False, "max_instances": 1, "misfire_grace_time": 10}
    return TwistedScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defautls=job_defaults,
        reactor=reactor,
    )


def create_twisted_server(port, metrics_path):
    root = Resource()
    root.putChild(metrics_path.encode("utf-8"), MetricsResource())

    factory = Site(root)
    reactor.listenTCP(port, factory)
    logging.info(f"listening port: {port}")
    return reactor


def setup_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics-path", type=str, default="/metrics")
    parser.add_argument("--listen-port", type=int, default=9300)
    parser.add_argument("--config-file", type=str, default="config.yml")
    return parser.parse_args()


def register_jobs(sched):
    for service in SERVICES:
        targets = []
        # expand target partterns if exists
        for target in service.targets:
            if is_parttern(target):
                # 展开 target pattern
                targets.extend(expand_patterns(target))
            else:
                targets.append(target)
        for target in targets:
            task = partial(run_check, service, target)
            task.__name__ = f"request[{service.name}, {target}]"
            sched.add_job(task, "interval", seconds=service.interval, misfire_grace_time=30)


def main():
    args = setup_parser()
    load_services(args.config_file)
    reactor = create_twisted_server(args.listen_port, args.metrics_path.lstrip("/"))
    sched = create_scheduler(reactor)
    register_jobs(sched)
    sched.start()
    reactor.run()


if __name__ == "__main__":
    main()
