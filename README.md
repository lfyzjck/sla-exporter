SLA Exporter
====

一个简化版本的黑盒监控组件，可以接入到 Prometheus 界定服务的可用性指标 (SLA)。
类似 [BlackBox Exporter](https://github.com/prometheus/blackbox_exporter) 但是可以自身调度请求而不是依赖 prometheus

## QuickStart

#### Start SLA-Exporter

```
$ sla-exporter -h
usage: main.py [-h] [--metrics-path METRICS_PATH] [--listen-port LISTEN_PORT] [--config-file CONFIG_FILE] [--module-config-file MODULE_CONFIG_FILE]

optional arguments:
  -h, --help            show this help message and exit
  --metrics-path METRICS_PATH
  --listen-port LISTEN_PORT
  --config-file CONFIG_FILE
```

#### Visit Metrics Path

```bash
$ curl localhost:9300/metrics
```

## Modules:

### http_2xx
请求 URL 如果返回 2xx 就认为成功, 支持 POST 请求

参数说明:

| Parameter Name | Default Value | Description |
| --- | --- | --- |
| http.method | GET | HTTP METHOD |
| http.body | None | body |
| http.headers | {} | MAP 类型，headers |
| valid_status_codes | [200] | 数组，合法的 response code |
| timeout | 10 | 超时时间 |
| no_follow_redirects | false | 不跟随 302 |

example:

```yaml
- name: frog-test
  module: http_2xx
  interval: 10
  module_config:
    http:
      method: POST
      headers:
        "Content-Type": "application/json"
      body: >
        {"head":{"userId":0.0,"device":2.0,"deviceId":"-1","appVersion":"1.0.0","screenWidth":851.0,"screenHeight":393.0,"osVersion":"10","manufacturer":"Yuanfudao","model":"YuanTiKu/4.17.0"},"entries":[{"productId":"000","timestamp":"1611560007","url":"/mock/test","net":0.0,"keyValues":[{"key":"subject","value":"2"},{"key":"userid","value":"0"},{"key":"type","value":"0"},{"key":"userAgent","value":"Mozilla/5.0 (Linux; Android 10; Redmi K20 Pro Premium Edition Build/QKQ1.190825.002; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/77.0.3865.120 MQQBrowser/6.2 TBS/045410 Mobile Safari/537.36 Zebra YuanTiKu/4.17.0"},{"key":"hostName","value":"localhost"}]}]}
  targets:
    - http://frog.yuanfudao.biz/statV2/plain
```

### script

执行 shell 命令，如果 exitcode 为 0 则认为成功

参数说明:

| Parameter Name | Default Value | Description |
| --- | --- | --- |
| valid_exit_codes | [0] | 合法的 exitcode |
| timeout | 60 | 超时时间 |

example:

```yaml
- name: script_nslookup
  module: script
  interval: 5
  targets:
    - nslookup google.com
```

### tcp

建立一个 TCP 连接并断开，主要探测端口是否存活

参数说明:

| Parameter Name | Default Value | Description |
| --- | --- | --- |
| timeout | 60 | 超时时间 |

example:

```yaml
- name: tcp_demo
  module: tcp
  interval: 10
  targets:
    - baidu.com:80
```

### presto

连接 presto 并查询 SQL

| Parameter Name | Default Value | Description |
| --- | --- | --- |
| host | - | Host |
| port | - | Port |
| user | - | UserName |
| password | None | Password |
| database | NOne | 对应 Presto 的 catalog |

example:

```yaml
  - name: presto-test
    module: presto
    interval: 60
    module_config:
      host: host
      port: 9030
      user: xxx
      password: xxx
      database: hive
    targets:
      - select 1;
```

### doris
连接 doris 集群 并查询 SQL, 有多个 fe 的情况下可以配置多个 host

| Parameter Name | Default Value | Description |
| --- | --- | --- |
| host | - | Host，支持多个 Host 用 , 隔开 |
| port | - | Port |
| user | - | UserName |
| password | None | Password |
| database | NOne | 对应 Presto 的 catalog |

example:

```yaml
- name: bigdata-doris-live
  module: doris
  module_config:
    host: fe1,fe2,fe3
    port: 9032
    user: xxx
    password: xxx
  targets:
    - select 1
```

## Full Examples

```yaml
services:
  - name: baidu.com
    module: http_2xx
    interval: 3
    targets:
      - https://baidu.com
  - name: demo_script
    module: script
    interval: 60
    targets:
      - nslookup google.com
  - name: tcp_demo
    module: tcp
    interval: 60
    targets:
      - host:port
  - name: doris-test
    module: doris
    interval: 5
    module_config:
      host: doris-hosts
      port: 9030
      user: admin
      password: admin123
    targets:
      - select 1
  - name: presto-test
    module: presto
    module_config:
      host: xxx
      port: xxx
      user: admin
    targets:
      - select 1
```

参数含义如下:

|参数|说明|
| --- | --- |
| name | 监控的服务名称 |
| module | 参见 Module 的说明 |
| module_config | module 的配置，每个 module 不同 |
| interval | 探测间隔，推荐不要过于频繁，>1min 最好 |
| targets | 监控目标列表. 如果是 http_2xx 则录入 url, 如果是 script 直接配置待执行的命令即可 |


会产生如下 prometheus 指标:

```
sla_request_success{group="baidu.com",target="https://baidu.com"} 1.0
sla_request_count_total{group="baidu.com",target="https://baidu.com"} 1.0
sla_request_duration{group="baidu.com",target="https://baidu.com"} 0.023493755608797073
```

## Developer Guide

### Prepare Environment

MacOS:

```
brew install python3
brew install poetry
cd /path/to/project
poetry install
```

### Packaging

```
poetry build
```