# -*- coding: utf-8 -*-
import __main__
import logging
import sys
from typing import *

import blcsdk
import blcsdk.models as sdk_models

import config
import database

logger = logging.getLogger('data-analytics.' + __name__)

_msg_handler: Optional['DataAnalyticsHandler'] = None


async def init():
    global _msg_handler
    _msg_handler = DataAnalyticsHandler()
    blcsdk.set_msg_handler(_msg_handler)

    # 初始化数据库
    database.get_connection()
    logger.info('Data analytics plugin initialized, database: %s', config.DB_PATH)

    # 获取已有房间
    try:
        blc_rooms = await blcsdk.get_rooms()
        for blc_room in blc_rooms:
            if blc_room.room_id is not None:
                database.add_room(
                    blc_room.room_id,
                    blc_room.room_key.type,
                    blc_room.room_key.value
                )
                logger.info('Added existing room: %d', blc_room.room_id)
    except (blcsdk.SdkError, AttributeError):
        pass


def shut_down():
    blcsdk.set_msg_handler(None)
    database.close_connection()
    logger.info('Data analytics plugin shut down')


class DataAnalyticsHandler(blcsdk.BaseHandler):
    def on_client_stopped(self, client: blcsdk.BlcPluginClient, exception: Optional[Exception]):
        logger.info('blivechat disconnected')
        __main__.start_shut_down()

    def _on_open_plugin_admin_ui(
        self, client: blcsdk.BlcPluginClient, message: sdk_models.OpenPluginAdminUiMsg, extra: sdk_models.ExtraData
    ):
        """处理管理按钮点击事件"""
        try:
            choice = self._show_admin_choice_dialog()
            if choice == 'stats':
                self._open_stats_page()
            elif choice == 'database':
                self._open_database_location()
        except Exception as e:
            logger.exception('Failed to handle admin UI request: %s', e)
    
    def _show_admin_choice_dialog(self) -> Optional[str]:
        """显示选择对话框，返回用户选择：'stats'、'database' 或 None"""
        try:
            import tkinter as tk
            from tkinter import messagebox
        except ImportError:
            # 如果没有 tkinter，使用命令行选择
            return self._show_console_choice()
        
        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口
        root.attributes('-topmost', True)  # 置顶
        
        # 创建选择对话框
        choice = None
        
        def choose_stats():
            nonlocal choice
            choice = 'stats'
            root.quit()
        
        def choose_database():
            nonlocal choice
            choice = 'database'
            root.quit()
        
        # 创建对话框窗口
        dialog = tk.Toplevel(root)
        dialog.title('数据分析插件管理')
        dialog.attributes('-topmost', True)
        dialog.resizable(False, False)
        
        # 居中显示
        dialog.update_idletasks()
        width = 400
        height = 200
        x = (dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (dialog.winfo_screenheight() // 2) - (height // 2)
        dialog.geometry(f'{width}x{height}+{x}+{y}')
        
        # 添加说明文字
        label = tk.Label(
            dialog,
            text='请选择要执行的操作：',
            font=('Microsoft YaHei', 10),
            pady=20
        )
        label.pack()
        
        # 添加按钮
        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=10)
        
        stats_btn = tk.Button(
            button_frame,
            text='📊 打开统计页面',
            command=choose_stats,
            width=20,
            height=2,
            font=('Microsoft YaHei', 9)
        )
        stats_btn.pack(side=tk.LEFT, padx=10)
        
        db_btn = tk.Button(
            button_frame,
            text='📁 打开数据库位置',
            command=choose_database,
            width=20,
            height=2,
            font=('Microsoft YaHei', 9)
        )
        db_btn.pack(side=tk.LEFT, padx=10)
        
        # 运行对话框
        dialog.mainloop()
        root.destroy()
        
        return choice
    
    def _show_console_choice(self) -> Optional[str]:
        """在控制台显示选择（当没有 tkinter 时）"""
        print('\n=== 数据分析插件管理 ===')
        print('1. 打开统计页面')
        print('2. 打开数据库位置')
        print('0. 取消')
        
        try:
            choice = input('\n请选择 (0-2): ').strip()
            if choice == '1':
                return 'stats'
            elif choice == '2':
                return 'database'
        except (EOFError, KeyboardInterrupt):
            pass
        
        return None
    
    def _open_stats_page(self):
        """在浏览器中打开统计页面"""
        import webbrowser
        import os
        
        web_path = os.path.abspath(config.WEB_PATH)
        
        # 检查文件是否存在
        if not os.path.exists(web_path):
            logger.error('Stats page not found: %s', web_path)
            if sys.platform == 'win32':
                try:
                    import tkinter.messagebox as messagebox
                    messagebox.showerror('错误', f'统计页面文件不存在：\n{web_path}')
                except ImportError:
                    print(f'错误：统计页面文件不存在：{web_path}')
            return
        
        # 转换为 file:// URL
        if sys.platform == 'win32':
            # Windows 路径需要特殊处理
            web_url = 'file:///' + web_path.replace('\\', '/')
        else:
            web_url = 'file://' + web_path
        
        try:
            webbrowser.open(web_url)
            logger.info('Opened stats page: %s', web_url)
        except Exception as e:
            logger.error('Failed to open stats page: %s', e)
            # 如果打开失败，尝试使用系统默认方式
            if sys.platform == 'win32':
                try:
                    os.startfile(web_path)
                except Exception as e2:
                    logger.error('Failed to open file: %s', e2)
    
    def _open_database_location(self):
        """打开数据库存储位置"""
        import os
        
        if sys.platform == 'win32':
            # Windows: 打开文件夹并选中数据库文件
            try:
                import subprocess
                subprocess.run(['explorer', '/select,', config.DB_PATH], check=False)
                logger.info('Opened database location: %s', config.DB_PATH)
            except Exception as e:
                logger.error('Failed to open database location: %s', e)
                # 备用方案：只打开文件夹
                try:
                    os.startfile(config.DATA_PATH)
                except Exception as e2:
                    logger.error('Failed to open data path: %s', e2)
        else:
            # Linux/Mac: 使用 xdg-open 或 open
            try:
                import subprocess
                if sys.platform == 'darwin':
                    subprocess.run(['open', '-R', config.DB_PATH], check=False)
                else:
                    subprocess.run(['xdg-open', os.path.dirname(config.DB_PATH)], check=False)
                logger.info('Opened database location: %s', config.DB_PATH)
            except Exception as e:
                logger.error('Failed to open database location: %s', e)
                logger.info('Database path: %s', config.DB_PATH)

    def _on_add_room(
        self, client: blcsdk.BlcPluginClient, message: sdk_models.AddRoomMsg, extra: sdk_models.ExtraData
    ):
        """添加房间"""
        if extra.is_from_plugin:
            return
        if extra.room_key is not None:
            # 此时room_id可能还是None，等ROOM_INIT时再添加
            pass

    def _on_room_init(
        self, client: blcsdk.BlcPluginClient, message: sdk_models.RoomInitMsg, extra: sdk_models.ExtraData
    ):
        """房间初始化"""
        if extra.is_from_plugin:
            return
        if message.is_success and extra.room_id is not None and extra.room_key is not None:
            database.add_room(
                extra.room_id,
                extra.room_key.type,
                extra.room_key.value
            )
            logger.info('Room initialized: %d', extra.room_id)

    def _on_add_text(
        self, client: blcsdk.BlcPluginClient, message: sdk_models.AddTextMsg, extra: sdk_models.ExtraData
    ):
        """收到弹幕"""
        if extra.is_from_plugin:
            return
        if extra.room_id is None:
            return

        try:
            database.add_danmaku(
                msg_id=message.id,
                room_id=extra.room_id,
                timestamp=message.timestamp,
                uid=message.uid,
                author_name=message.author_name,
                author_type=message.author_type,
                author_level=message.author_level,
                content=message.content,
                translation=message.translation,
                is_gift_danmaku=message.is_gift_danmaku,
                is_newbie=message.is_newbie,
                is_mobile_verified=message.is_mobile_verified,
                privilege_type=message.privilege_type,
                medal_level=message.medal_level,
                medal_name=message.medal_name,
                content_type=message.content_type,
                avatar_url=message.avatar_url
            )
        except Exception as e:
            logger.exception('Failed to save danmaku: %s', e)

    def _on_add_gift(
        self, client: blcsdk.BlcPluginClient, message: sdk_models.AddGiftMsg, extra: sdk_models.ExtraData
    ):
        """有人送礼"""
        if extra.is_from_plugin:
            return
        if extra.room_id is None:
            return

        try:
            database.add_gift(
                msg_id=message.id,
                room_id=extra.room_id,
                timestamp=message.timestamp,
                uid=message.uid,
                author_name=message.author_name,
                gift_id=message.gift_id,
                gift_name=message.gift_name,
                gift_icon_url=message.gift_icon_url,
                num=message.num,
                total_coin=message.total_coin,
                total_free_coin=message.total_free_coin,
                privilege_type=message.privilege_type,
                medal_level=message.medal_level,
                medal_name=message.medal_name,
                avatar_url=message.avatar_url
            )
        except Exception as e:
            logger.exception('Failed to save gift: %s', e)

    def _on_add_member(
        self, client: blcsdk.BlcPluginClient, message: sdk_models.AddMemberMsg, extra: sdk_models.ExtraData
    ):
        """有人上舰"""
        if extra.is_from_plugin:
            return
        if extra.room_id is None:
            return

        try:
            database.add_member(
                msg_id=message.id,
                room_id=extra.room_id,
                timestamp=message.timestamp,
                uid=message.uid,
                author_name=message.author_name,
                privilege_type=message.privilege_type,
                num=message.num,
                unit=message.unit,
                total_coin=message.total_coin,
                medal_level=message.medal_level,
                medal_name=message.medal_name,
                avatar_url=message.avatar_url
            )
        except Exception as e:
            logger.exception('Failed to save member: %s', e)

    def _on_add_super_chat(
        self, client: blcsdk.BlcPluginClient, message: sdk_models.AddSuperChatMsg, extra: sdk_models.ExtraData
    ):
        """醒目留言"""
        if extra.is_from_plugin:
            return
        if extra.room_id is None:
            return

        try:
            database.add_super_chat(
                msg_id=message.id,
                room_id=extra.room_id,
                timestamp=message.timestamp,
                uid=message.uid,
                author_name=message.author_name,
                price=message.price,
                content=message.content,
                translation=message.translation,
                privilege_type=message.privilege_type,
                medal_level=message.medal_level,
                medal_name=message.medal_name,
                avatar_url=message.avatar_url
            )
        except Exception as e:
            logger.exception('Failed to save super chat: %s', e)

