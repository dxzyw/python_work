import re
from prometheus_client import Gauge, CollectorRegistry
import pymysql
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')

# 创建一个字典来存储已创建的指标
metrics_dict = {}

def sanitize_metric_name(name):
    """
    将中文名称转换为合法的 Prometheus 指标名称
    1. 转换为拼音（可选）
    2. 移除非法字符
    3. 确保名称符合规范
    """
    # 移除所有非字母数字的字符，用下划线替换
    name = re.sub(r'[^a-zA-Z0-9]', '_', name)
    # 确保不以数字开头
    if name[0].isdigit():
        name = 'n_' + name
    # 移除连续的下划线
    name = re.sub(r'_+', '_', name)
    # 移除首尾的下划线
    name = name.strip('_')
    return name.lower()

def get_or_create_metric(db_name):
    """
    获取或创建新的监控指标
    """
    try:
        if db_name not in metrics_dict:
            metric_name = f'mysql_count_{sanitize_metric_name(db_name)}'
            metric_help = f'Count of records for {db_name}'
            logging.info(f"Creating new metric: {metric_name}")
            # 添加 system 标签
            metrics_dict[db_name] = Gauge(metric_name, metric_help, ['env', 'display_name', 'system'])
        return metrics_dict[db_name]
    except Exception as e:
        logging.error(f"Error creating metric for {db_name}: {e}")
        raise

def update_metrics(config):
    try:
        # 创建规范的指标名称
        base_name = sanitize_metric_name(config["name"])
        system_name = sanitize_metric_name(config["system"])
        env_name = sanitize_metric_name(config["env"])
        
        metric_name = f'mysql_count_{base_name}_{system_name}_{env_name}'
        
        # 检查指标是否已存在
        if metric_name not in metrics_dict:
            metric = Gauge(
                metric_name,
                f'MySQL query result for {config["name"]}',
                ['display_name', 'system', 'env']
            )
            metrics_dict[metric_name] = metric
        else:
            metric = metrics_dict[metric_name]

        # 执行查询并更新指标值
        try:
            conn = pymysql.connect(
                host=config['host'],
                port=int(config['port']),
                user=config['user'],
                password=config['password'],
                database=config['database']
            )
            
            with conn.cursor() as cursor:
                cursor.execute(config['query'])
                result = cursor.fetchone()
                
                # 确保结果是一个数字
                if result is not None:
                    # 如果结果是元组，取第一个元素
                    value = result[0] if isinstance(result, tuple) else result
                    # 转换为浮点数
                    value = float(value)
                    
                    metric.labels(
                        display_name=config['name'],
                        system=config['system'],
                        env=config['env']
                    ).set(value)
                    
                    logging.info(f"Successfully updated metric {metric_name} with value {value}")
                else:
                    logging.warning(f"Query returned no result for {config['name']}")
                    
            conn.close()
            
        except Exception as e:
            logging.error(f"Error executing query for {config['name']}: {str(e)}")
            if 'conn' in locals():
                conn.close()
            
    except Exception as e:
        logging.error(f"Error creating metric for {config['name']}: {str(e)}")

def get_metrics():
    """
    获取所有当前的 metrics 值
    """
    try:
        current_metrics = []
        for name, metric in metrics_dict.items():
            for sample in metric._samples():
                current_metrics.append({
                    'name': name,
                    'value': sample[2],  # sample[2] 是值
                    'env': sample[1]['env']  # sample[1] 是标签字典
                })
        return current_metrics
    except Exception as e:
        logging.error(f"Error getting metrics: {e}")
        return []