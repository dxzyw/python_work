from app import app, db
from models import MonitorConfig

def update_existing_data():
    with app.app_context():
        try:
            # 获取所有现有配置
            configs = MonitorConfig.query.all()
            
            # 更新系统名为默认值
            for config in configs:
                if not config.system:
                    config.system = '默认系统'  # 或其他默认值
            
            # 提交更改
            db.session.commit()
            print("数据更新成功")
            
        except Exception as e:
            db.session.rollback()
            print(f"数据更新失败: {e}")

if __name__ == '__main__':
    update_existing_data() 