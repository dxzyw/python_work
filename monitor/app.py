from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from apscheduler.schedulers.background import BackgroundScheduler
from prometheus_client import make_wsgi_app, generate_latest, CONTENT_TYPE_LATEST
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple
from models import db, MonitorConfig
import mysql_mo
import pymysql
from prometheus_client.parser import text_string_to_metric_families
import requests
from datetime import datetime
import logging

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///monitor.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# 初始化 Flask-Migrate
migrate = Migrate(app, db)

# 创建调度器
scheduler = BackgroundScheduler()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/config', methods=['GET', 'POST'])
def config():
    if request.method == 'POST':
        try:
            data = request.json
            # 验证必填字段
            required_fields = ['name', 'system', 'host', 'port', 'user', 'password', 'database', 'env', 'query']
            for field in required_fields:
                if not data.get(field):
                    return jsonify({
                        'status': 'error',
                        'message': f'缺少必填字字段: {field}'
                    }), 400

            # 测试数据库连接
            try:
                conn = pymysql.connect(
                    host=data['host'],
                    port=int(data['port']),
                    user=data['user'],
                    password=data['password'],
                    database=data['database'],
                    connect_timeout=5
                )
                conn.close()
            except Exception as e:
                return jsonify({
                    'status': 'error',
                    'message': f'数据库连接测试失败: {str(e)}'
                }), 400

            # 创建新配置
            config = MonitorConfig(
                name=data['name'],
                system=data['system'],
                host=data['host'],
                port=data['port'],
                user=data['user'],
                password=data['password'],
                database=data['database'],
                env=data['env'],
                query=data['query']
            )

            # 保存到数据库
            db.session.add(config)
            db.session.commit()

            # 立即创建 metric 并执行一次更新
            config_dict = {
                'name': config.name,
                'system': config.system,  # 添加系统名
                'host': config.host,
                'port': config.port,
                'user': config.user,
                'password': config.password,
                'database': config.database,
                'env': config.env,
                'query': config.query
            }
            mysql_mo.update_metrics(config_dict)

            # 重新加载监控任务
            reload_monitor_jobs()

            return jsonify({
                'status': 'success',
                'message': '配置保存成功'
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': f'保存配置失败: {str(e)}'
            }), 500

    # GET 请求处理
    try:
        configs = db.session.query(MonitorConfig).all()
        return render_template('config.html', configs=configs)
    except Exception as e:
        return render_template('error.html', error=str(e)), 500

@app.route('/config/test', methods=['POST'])
def test_connection():
    """测试数据库连接"""
    try:
        data = request.json
        conn = pymysql.connect(
            host=data['host'],
            port=int(data['port']),
            user=data['user'],
            password=data['password'],
            database=data['database'],
            connect_timeout=5
        )
        conn.close()
        return jsonify({
            'status': 'success',
            'message': '连接测试成功'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'连接测试失败: {str(e)}'
        }), 400

def reload_monitor_jobs():
    """重新加载所有监控任务"""
    try:
        # 清除现有任务
        scheduler.remove_all_jobs()
        logging.info("Cleared existing jobs")
        
        # 重新加载配置并创建新任务
        configs = db.session.query(MonitorConfig).all()
        for config in configs:
            config_dict = {
                'name': config.name,
                'system': config.system,  # 添加系统名
                'host': config.host,
                'port': config.port,
                'user': config.user,
                'password': config.password,
                'database': config.database,
                'env': config.env,
                'query': config.query
            }
            
            # 立即执行一次
            mysql_mo.update_metrics(config_dict)
            
            # 添加定时任务
            scheduler.add_job(
                mysql_mo.update_metrics,
                'interval',
                minutes=1,
                args=[config_dict],
                id=f'monitor_{config.id}',
                replace_existing=True
            )
            logging.info(f"Added job for {config.name}")
        return True
    except Exception as e:
        logging.error(f"Error reloading monitor jobs: {e}")
        return False

@app.route('/metrics')
def metrics():
    """
    提供 Prometheus 格式的监控数据
    """
    try:
        return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}
    except Exception as e:
        logging.error(f"Error generating metrics: {e}")
        return str(e), 500

@app.route('/metrics_data')
def metrics_data():
    """
    提供 JSON 格式的监控数据
    """
    try:
        metrics_list = []
        for family in text_string_to_metric_families(generate_latest().decode('utf-8')):
            if family.name.startswith('mysql_count_'):
                for sample in family.samples:
                    metrics_list.append({
                        'name': family.name.replace('mysql_count_', ''),
                        'system': sample.labels.get('system', '未知系统'),  # 添加system字段
                        'display_name': sample.labels.get('display_name', ''),
                        'env': sample.labels.get('env', 'unknown'),
                        'value': sample.value,
                        'timestamp': datetime.now().isoformat()
                    })
        return jsonify(metrics_list)
    except Exception as e:
        logging.error(f"Error getting metrics data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/config/<int:id>', methods=['GET'])
def get_config(id):
    """获取单个配置"""
    try:
        with app.app_context():
            config = db.session.query(MonitorConfig).filter(MonitorConfig.id == id).first()
            
            if not config:
                return jsonify({
                    'status': 'error',
                    'message': '配置不存在'
                }), 404

            # 返回完整配置信息，包括密码
            config_dict = {
                'id': config.id,
                'name': config.name,
                'system': config.system,
                'host': config.host,
                'port': config.port,
                'user': config.user,
                'password': config.password,  # 保留密码
                'database': config.database,
                'env': config.env,
                'query': config.query
            }

            return jsonify({
                'status': 'success',
                'data': config_dict
            })

    except Exception as e:
        logging.error(f"获取配置失败: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'获取配置失败: {str(e)}'
        }), 500

@app.route('/config/batch_import', methods=['POST'])
def batch_import_config():
    try:
        configs = request.json
        
        # 检查名称唯一性
        with app.app_context():
            existing_configs = db.session.query(MonitorConfig).all()
            existing_names = set((c.name, c.system, c.env) for c in existing_configs)
            
            for config in configs:
                config_key = (config['name'], config['system'], config['env'])
                if config_key in existing_names:
                    return jsonify({
                        'status': 'error',
                        'message': f'配置已存在: {config["name"]} ({config["system"]} - {config["env"]})'
                    }), 400

                # 测试数据库连接
                try:
                    conn = pymysql.connect(
                        host=config['host'],
                        port=int(config['port']),
                        user=config['user'],
                        password=config['password'],
                        database=config['database'],
                        connect_timeout=5
                    )
                    conn.close()
                except Exception as e:
                    return jsonify({
                        'status': 'error',
                        'message': f'数据库连接测试失败 ({config["name"]}): {str(e)}'
                    }), 400

                # 创建配置
                new_config = MonitorConfig(
                    name=config['name'],
                    system=config['system'],
                    host=config['host'],
                    port=config['port'],
                    user=config['user'],
                    password=config['password'],
                    database=config['database'],
                    env=config['env'],
                    query=config['query']
                )
                db.session.add(new_config)

            try:
                # 提交事务
                db.session.commit()
                
                # 重新加载监控任务
                reload_monitor_jobs()

                return jsonify({
                    'status': 'success',
                    'message': '配置导入成功'
                })
            except Exception as e:
                db.session.rollback()
                return jsonify({
                    'status': 'error',
                    'message': f'保存配置失败: {str(e)}'
                }), 500

    except Exception as e:
        logging.error(f"导入配置失败: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'导入失败: {str(e)}'
        }), 500

@app.route('/config/<int:id>', methods=['PUT'])
def update_config(id):
    """更新配置"""
    try:
        config = db.session.query(MonitorConfig).get(id)
        if not config:
            return jsonify({
                'status': 'error',
                'message': '配置不存在'
            }), 404

        data = request.json
        
        # 更新配置
        for key in ['name', 'system', 'host', 'port', 'user', 'password', 'database', 'env', 'query']:
            if key in data:
                setattr(config, key, data[key])
        
        db.session.commit()
        
        # 更新监控任务
        config_dict = {
            'name': config.name,
            'system': config.system,  # 添加系统名
            'host': config.host,
            'port': config.port,
            'user': config.user,
            'password': config.password,
            'database': config.database,
            'env': config.env,
            'query': config.query
        }
        
        # 重新加载监控任务
        reload_monitor_jobs()
        
        return jsonify({
            'status': 'success',
            'message': '配置更新成功'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/config/<int:id>', methods=['DELETE'])
def delete_config(id):
    """删除配置"""
    try:
        config = db.session.query(MonitorConfig).get(id)
        if not config:
            return jsonify({
                'status': 'error',
                'message': '配置不存在'
            }), 404
            
        db.session.delete(config)
        db.session.commit()
        
        # 重新加载监控任务
        reload_monitor_jobs()
        
        return jsonify({
            'status': 'success',
            'message': '配置删除成功'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500 

if __name__ == '__main__':
    # 初始化数据库
    with app.app_context():
        db.create_all()
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # 启动调度器
    scheduler.start()
    logging.info("Scheduler started")
    
    # 初始化载监控任务
    with app.app_context():
        reload_monitor_jobs()
    
    # 合并Prometheus metrics接口
    app_dispatch = DispatcherMiddleware(app, {
        '/metrics': make_wsgi_app()
    })
    
    run_simple('0.0.0.0', 8001, app_dispatch, use_reloader=True) 