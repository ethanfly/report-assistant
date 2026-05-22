@echo off
rem 清除 Windows 图标缓存（小T日报助手图标更新后必须执行才能立即看到大图标变化）
rem 用法：管理员身份运行此脚本

echo 正在清理 Windows 图标缓存...

rem 1) 杀掉 explorer，否则它会锁住缓存文件
taskkill /f /im explorer.exe

rem 2) 删除缓存
del /a /q "%LocalAppData%\IconCache.db" 2>nul
del /a /f /q "%LocalAppData%\Microsoft\Windows\Explorer\iconcache_*.db" 2>nul
del /a /f /q "%LocalAppData%\Microsoft\Windows\Explorer\thumbcache_*.db" 2>nul

rem 3) 重启 explorer
start explorer.exe

echo 图标缓存已清除，重新登录或注销后桌面图标会刷新到最新版本。
pause
