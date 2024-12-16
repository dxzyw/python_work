from flask_migrate import Migrate
from app import app, db
from models import MonitorConfig

migrate = Migrate(app, db)

if __name__ == '__main__':
    with app.app_context():
        # 初始化迁移
        from flask_migrate import init, migrate, upgrade
        import os
        
        # 如果migrations目录不存在，初始化迁移
        if not os.path.exists('migrations'):
            init()
        
        # 创建迁移脚本
        migrate()
        
        # 执行迁移
        upgrade() 