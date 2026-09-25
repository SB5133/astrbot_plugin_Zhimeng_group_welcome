import json
import os
import aiohttp
import random
import asyncio
from pathlib import Path

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.core import AstrBotConfig
import astrbot.api.message_components as Comp

DATA_DIR = Path("data/zhiMeng_group_welcome")


async def is_valid_image_url(url: str):
    """检查网络图片 URL 是否有效"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(url, timeout=5) as response:
                return response.status == 200
    except Exception as e:
        logger.error(f"Error checking image URL: {e}")
        return False


@register("astrbot_plugin_Zhimeng_group_welcome", "稚梦(SB5133)", "入群/退群消息提示，支持每个群单独配置文字、图片和开关", "1.2.0")
class MyPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.is_send_welcome = config.get("is_send_welcome", False)
        self.is_at = config.get("is_at", True)
        self.is_send_bye = config.get("is_send_bye", True)
        self.is_debug = config.get("is_debug", False)
        self.black_groups = config.get("black_groups", [])
        self.white_groups = config.get("white_groups", [])
        self.welcome_text = config.get("welcome_text", "欢迎新成员加入！")
        self.welcome_img = config.get("welcome_img", [])
        self.bye_text = config.get("bye_text", "群友{username}({userid})退群了!")
        self.bye_img = config.get("bye_img", [])
        self.kick_text = config.get("kick_text", "群友{username}({userid})被管理员{operator_name}({operator_id})踢出群了!")
        self.kick_img = config.get("kick_img", [])

        # 数据目录
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.json_path = DATA_DIR / "data.json"

    async def initialize(self):
        pass

    async def terminate(self):
        pass

    # ---------- 群配置存取 ----------

    def _load_data(self) -> dict:
        if self.json_path.exists():
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
            except Exception as e:
                logger.error(f"读取群配置失败: {e}")
        return {}

    def _save_data(self, data: dict):
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _get_group_conf(self, group_id) -> dict:
        conf = self._load_data().get(str(group_id))
        return conf if isinstance(conf, dict) else {}

    def _set_group_conf(self, group_id, key: str, value):
        data = self._load_data()
        conf = data.get(str(group_id))
        if not isinstance(conf, dict):
            conf = {}
            data[str(group_id)] = conf
        conf[key] = value
        self._save_data(data)

    # ---------- 通用工具 ----------

    async def _resolve_image(self, image_ref):
        """把图片引用（URL 或本地文件名）解析为消息组件，失败返回 None"""
        if not image_ref:
            return None
        image_ref = str(image_ref)
        if image_ref.startswith(("http://", "https://")):
            if await is_valid_image_url(image_ref):
                return Comp.Image.fromURL(image_ref)
            logger.warning(f"Invalid image URL: {image_ref}")
            return None
        local_path = DATA_DIR / image_ref
        if local_path.exists():
            return Comp.Image.fromFileSystem(str(local_path))
        logger.warning(f"Local image not found: {local_path}")
        return None

    def check_send(self, group_id) -> bool:
        """全局黑白名单"""
        if self.black_groups and str(group_id) in self.black_groups:
            return False
        if self.white_groups and str(group_id) not in self.white_groups:
            return False
        return True

    # ---------- 群配置命令 ----------

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("设置欢迎消息", alias={"设置入群信息", "设置入群提示", "设置欢迎信息"})
    async def set_hello_message(self, event: AstrMessageEvent, message: str):
        """设置当前群欢迎文字"""
        if event.is_private_chat():
            yield event.plain_result("请在群聊中使用此命令")
            return
        self._set_group_conf(event.get_group_id(), "welcome_text", message)
        yield event.plain_result(f"本群欢迎消息已设置为：{message.replace(chr(92) + 'n', chr(10))}")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("设置欢迎图片", alias={"设置入群图片", "设置入群欢迎图片"})
    async def set_hello_image(self, event: AstrMessageEvent, message: str):
        """设置当前群欢迎图片（网络图片URL或 data 目录下的本地文件名）"""
        if event.is_private_chat():
            yield event.plain_result("请在群聊中使用此命令")
            return
        self._set_group_conf(event.get_group_id(), "welcome_img", message)
        yield event.plain_result(f"本群欢迎图片已设置为：{message}")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("设置退群消息", alias={"设置告别消息", "设置退群提示"})
    async def set_bye_message(self, event: AstrMessageEvent, message: str):
        """设置当前群退群文字，支持 {username} {userid} 占位符"""
        if event.is_private_chat():
            yield event.plain_result("请在群聊中使用此命令")
            return
        self._set_group_conf(event.get_group_id(), "bye_text", message)
        yield event.plain_result(f"本群退群消息已设置为：{message.replace(chr(92) + 'n', chr(10))}")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("设置退群图片", alias={"设置告别图片"})
    async def set_bye_image(self, event: AstrMessageEvent, message: str):
        """设置当前群退群图片"""
        if event.is_private_chat():
            yield event.plain_result("请在群聊中使用此命令")
            return
        self._set_group_conf(event.get_group_id(), "bye_img", message)
        yield event.plain_result(f"本群退群图片已设置为：{message}")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("设置踢人消息", alias={"设置踢群消息"})
    async def set_kick_message(self, event: AstrMessageEvent, message: str):
        """设置当前群被踢文字，支持 {username} {userid} {operator_name} {operator_id} 占位符"""
        if event.is_private_chat():
            yield event.plain_result("请在群聊中使用此命令")
            return
        self._set_group_conf(event.get_group_id(), "kick_text", message)
        yield event.plain_result(f"本群踢人消息已设置为：{message.replace(chr(92) + 'n', chr(10))}")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("设置踢人图片", alias={"设置踢群图片"})
    async def set_kick_image(self, event: AstrMessageEvent, message: str):
        """设置当前群被踢图片"""
        if event.is_private_chat():
            yield event.plain_result("请在群聊中使用此命令")
            return
        self._set_group_conf(event.get_group_id(), "kick_img", message)
        yield event.plain_result(f"本群踢人图片已设置为：{message}")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("开启本群提醒", alias={"开启入群退群提醒"})
    async def enable_group(self, event: AstrMessageEvent):
        """开启当前群的入群/退群提醒"""
        if event.is_private_chat():
            yield event.plain_result("请在群聊中使用此命令")
            return
        self._set_group_conf(event.get_group_id(), "enabled", True)
        yield event.plain_result("已开启本群入群/退群提醒")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("关闭本群提醒", alias={"关闭入群退群提醒"})
    async def disable_group(self, event: AstrMessageEvent):
        """关闭当前群的入群/退群提醒（不影响全局黑白名单）"""
        if event.is_private_chat():
            yield event.plain_result("请在群聊中使用此命令")
            return
        self._set_group_conf(event.get_group_id(), "enabled", False)
        yield event.plain_result("已关闭本群入群/退群提醒")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("查看本群配置", alias={"查看群配置"})
    async def get_group_conf(self, event: AstrMessageEvent):
        """查看当前群的全部自定义配置"""
        if event.is_private_chat():
            yield event.plain_result("请在群聊中使用此命令")
            return
        group_id = event.get_group_id()
        conf = self._get_group_conf(group_id)
        if not conf:
            yield event.plain_result("当前群没有单独配置，全部使用全局配置")
            return

        lines = [f"群 {group_id} 的单独配置："]
        mapping = {
            "welcome_text": "欢迎文字",
            "welcome_img": "欢迎图片",
            "bye_text": "退群文字",
            "bye_img": "退群图片",
            "kick_text": "踢人文字",
            "kick_img": "踢人图片",
        }
        for key, label in mapping.items():
            if key in conf:
                lines.append(f"{label}：{str(conf[key]).replace(chr(92) + 'n', chr(10))}")
        if "enabled" in conf:
            lines.append(f"提醒开关：{'开启' if conf['enabled'] else '关闭'}")
        yield event.plain_result("\n".join(lines))

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("清除本群配置", alias={"重置本群配置", "删除本群配置"})
    async def clear_group_conf(self, event: AstrMessageEvent):
        """清除当前群的全部单独配置，恢复使用全局配置"""
        if event.is_private_chat():
            yield event.plain_result("请在群聊中使用此命令")
            return
        group_id = str(event.get_group_id())
        data = self._load_data()
        if group_id in data:
            del data[group_id]
            self._save_data(data)
            yield event.plain_result("已清除本群单独配置，恢复使用全局配置")
        else:
            yield event.plain_result("当前群本来就没有单独配置")

    @filter.command("查看欢迎消息", alias={"查看入群信息", "查看入群提示", "查看欢迎信息"})
    async def get_hello_message(self, event: AstrMessageEvent):
        """查看当前群欢迎文字（含全局兜底）"""
        if event.is_private_chat():
            yield event.plain_result("请在群聊中使用此命令")
            return
        conf = self._get_group_conf(event.get_group_id())
        msg = str(conf.get("welcome_text", self.welcome_text)).replace("\\n", "\n")
        yield event.plain_result(f"欢迎消息为：{msg}")

    @filter.command("查看欢迎图片", alias={"查看入群图片", "查看入群欢迎图片"})
    async def get_hello_image(self, event: AstrMessageEvent):
        """查看当前群欢迎图片"""
        if event.is_private_chat():
            yield event.plain_result("请在群聊中使用此命令")
            return
        conf = self._get_group_conf(event.get_group_id())
        image_path = conf.get("welcome_img")
        if not image_path and self.welcome_img:
            image_path = random.choice(self.welcome_img)
        if not image_path:
            yield event.plain_result("当前群没有设置欢迎图片")
            return
        img = await self._resolve_image(image_path)
        if img:
            yield event.chain_result([img])
        else:
            yield event.plain_result(f"当前群设置的欢迎图片无效：{image_path}")

    # ---------- 事件处理 ----------

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def handle_group_add(self, event: AstrMessageEvent):
        """处理入群和退群事件"""
        if not hasattr(event, "message_obj") or not hasattr(event.message_obj, "raw_message"):
            return

        raw_message = event.message_obj.raw_message
        if not raw_message or not isinstance(raw_message, dict):
            return
        logger.debug(f"Received raw message: {raw_message}")
        if raw_message.get("post_type") != "notice":
            return

        if raw_message.get("notice_type") == "group_increase":
            if not self.is_send_welcome:
                return
            group_id = raw_message.get("group_id")
            if not self.check_send(group_id) or self._get_group_conf(group_id).get("enabled") is False:
                return
            user_id = raw_message.get("user_id")

            # 跳过机器人自己进群
            self_id = event.get_self_id()
            if str(user_id) == str(self_id):
                logger.debug(f"Bot self joined group {group_id}, skipping welcome message")
                return
            # 延迟1.5s，等待 QQ 服务器同步新成员信息，避免astrbot解析Comp.at超时
            await asyncio.sleep(1.5)

            group_conf = self._get_group_conf(group_id)
            welcome_message = str(group_conf.get("welcome_text", self.welcome_text)).replace("\\n", "\n")
            image_ref = group_conf.get("welcome_img") or (random.choice(self.welcome_img) if self.welcome_img else None)
            img = await self._resolve_image(image_ref)

            chain = [Comp.At(qq=user_id) if self.is_at else Comp.Plain(""), Comp.Plain(welcome_message)]
            if img:
                chain.append(img)
            yield event.chain_result(chain)

        elif raw_message.get("notice_type") == "group_decrease":
            if not self.is_send_bye:
                return
            group_id = raw_message.get("group_id")
            if not self.check_send(group_id) or self._get_group_conf(group_id).get("enabled") is False:
                return
            user_id = raw_message.get("user_id")
            sub_type = raw_message.get("sub_type")

            from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
            assert isinstance(event, AiocqhttpMessageEvent)
            client = event.bot
            info = await client.get_stranger_info(user_id=user_id, no_cache=True)
            username = info.get("nickname", "未知用户")

            group_conf = self._get_group_conf(group_id)
            if sub_type == "kick":
                # 被踢出群
                operator_id = raw_message.get("operator_id")
                operator_info = await client.get_stranger_info(user_id=operator_id, no_cache=True)
                operator_name = operator_info.get("nickname", "未知管理员")

                message = str(group_conf.get("kick_text", self.kick_text)).replace("\\n", "\n").format(
                    username=username,
                    userid=user_id,
                    operator_name=operator_name,
                    operator_id=operator_id
                )
                image_ref = group_conf.get("kick_img") or (random.choice(self.kick_img) if self.kick_img else None)
            else:
                # 主动退群 (sub_type == "leave" 或其他)
                message = str(group_conf.get("bye_text", self.bye_text)).replace("\\n", "\n").format(
                    username=username, userid=user_id
                )
                image_ref = group_conf.get("bye_img") or (random.choice(self.bye_img) if self.bye_img else None)

            img = await self._resolve_image(image_ref)
            if img:
                yield event.chain_result([Comp.Plain(message), img])
            else:
                yield event.plain_result(message)
