# 项目介绍

<h2 align="center">
  FastAPI-Amis-Admin-Nav
</h2>
<p align="center">
    <em>FastAPI-Amis-Admin-Nav是一个基于FastAPI-Amis-Admin并且为FastAPI-Amis-Admin提供可视化导航页面管理的拓展库.</em><br/>

</p>
<p align="center">
    <a href="https://github.com/amisadmin/fastapi_amis_admin/actions/workflows/pytest.yml" target="_blank">
        <img src="https://github.com/amisadmin/fastapi_amis_admin/actions/workflows/pytest.yml/badge.svg" alt="Pytest">
    </a>
    <a href="https://pypi.org/project/fastapi_amis_admin_nav" target="_blank">
        <img src="https://badgen.net/pypi/v/fastapi-amis-admin-nav?color=blue" alt="Package version">
    </a>
    <a href="https://pepy.tech/project/fastapi-amis-admin-nav" target="_blank">
        <img src="https://pepy.tech/badge/fastapi-amis-admin-nav" alt="Downloads">
    </a>
    <a href="https://gitter.im/amisadmin/fastapi-amis-admin">
        <img src="https://badges.gitter.im/amisadmin/fastapi-amis-admin.svg" alt="Chat on Gitter"/>
    </a>
    <a href="https://jq.qq.com/?_wv=1027&k=U4Dv6x8W" target="_blank">
        <img src="https://badgen.net/badge/qq%E7%BE%A4/229036692/orange" alt="229036692">
    </a>
</p>
<p align="center">
  <a href="https://github.com/amisadmin/fastapi_amis_admin_nav" target="_blank">源码</a>
  ·
  <a href="http://user-auth.demo.amis.work/" target="_blank">在线演示</a>
  ·
  <a href="http://docs.amis.work" target="_blank">文档</a>
  ·
  <a href="http://docs.gh.amis.work" target="_blank">文档打不开？</a>
</p>

------

`fastapi-amis-admin-nav`是一个基于FastAPI-Amis-Admin并且为FastAPI-Amis-Admin提供可视化导航页面管理的拓展库.

## 安装

```bash
pip install fastapi-amis-admin-nav
```

## 简单示例

```python
from fastapi import FastAPI
from fastapi_amis_admin.admin.settings import Settings
from fastapi_amis_admin.admin.site import AdminSite
from fastapi_amis_admin_nav.admin import NavPageAdmin
from sqlmodel import SQLModel

# 创建FastAPI应用
app = FastAPI()

# 创建AdminSite实例
site = AdminSite(settings=Settings(database_url_async='sqlite+aiosqlite:///amisadmin.db'))

# 注册导航页面管理
site.register_admin(NavPageAdmin)

# 挂载后台管理系统
site.mount_app(app)


# 创建初始化数据库表
@app.on_event("startup")
async def startup():
    # 创建数据库表
    await site.db.async_run_sync(SQLModel.metadata.create_all, is_session=False)
    # 运行后台管理系统启动事件
    await site.fastapi.router.startup()


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, debug=True)

```


## 界面预览

- Open `http://127.0.0.1:8000/admin/` in your browser:

![ModelAdmin](https://s2.loli.net/2022/03/20/ItgFYGUONm1jCz5.png)


## 许可协议

- `fastapi-amis-admin`基于`Apache2.0`开源免费使用，可以免费用于商业用途，但请在展示界面中明确显示关于FastAPI-Amis-Admin的版权信息.
