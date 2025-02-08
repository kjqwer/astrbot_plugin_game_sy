from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import *
from astrbot.api.event import MessageChain
import random
import asyncio
from typing import Dict, List, Set

@register("huanju", "kjqwdw", "欢乐21点", "1.0.0", "https://github.com/kjqwer/astrbot_plugin_game_sy")  
class HuanJuPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

        self.game_rooms: Dict[str, Dict] = {}
        # 21点只需要一副牌，不需要大小王
        self.cards = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
        self.suits = ['♠', '♥', '♣', '♦']
        self.bot_names = ["机器人小A", "机器人小B", "机器人小C"]  # 机器人名字列表
        
    @filter.command_group("hj")
    def huanju(self):
        '''欢乐21点指令组'''
        pass

    @huanju.command("create")
    async def create_game(self, event: AstrMessageEvent):
        '''创建一个21点游戏房间'''
        group_id = event.message_obj.group_id
        if not group_id:
            yield event.plain_result("请在群聊中使用此命令！")
            return
            
        if group_id in self.game_rooms:
            yield event.plain_result("当前群已存在牌局！")
            return
            
        self.game_rooms[group_id] = {
            "players": set(),
            "status": "waiting",  # waiting, playing
            "current_cards": {},  # 玩家手牌
            "creator": event.get_sender_id(),
            "current_player": None,  # 当前回合玩家
            "player_status": {},  # 玩家状态（要牌/停牌）
            "points": {}  # 玩家点数
        }
        
        yield event.plain_result("21点游戏房间创建成功！请使用 /hj join 加入游戏，2-4人即可开始。")

    @huanju.command("join")
    async def join_game(self, event: AstrMessageEvent):
        '''加入游戏'''
        group_id = event.message_obj.group_id
        if not group_id:
            yield event.plain_result("请在群聊中使用此命令！")
            return
            
        if group_id not in self.game_rooms:
            yield event.plain_result("当前群未创建牌局！请使用 /hj create 创建")
            return
            
        room = self.game_rooms[group_id]
        if room["status"] != "waiting":
            yield event.plain_result("牌局已经开始，无法加入！")
            return
            
        player_id = event.get_sender_id()
        if player_id in room["players"]:
            yield event.plain_result("你已经在牌局中了！")
            return
            
        if len(room["players"]) >= 4:
            yield event.plain_result("房间已满！")
            return
            
        room["players"].add(player_id)
        yield event.plain_result(f"加入成功！当前玩家数: {len(room['players'])}/4")
        
        if len(room["players"]) >= 2:
            yield event.plain_result("人数已达2人，可以使用 /hj start 开始游戏")

    @huanju.command("addbot")
    async def add_bot(self, event: AstrMessageEvent):
        '''添加机器人玩家'''
        group_id = event.message_obj.group_id
        if not group_id:
            yield event.plain_result("请在群聊中使用此命令！")
            return
            
        if group_id not in self.game_rooms:
            yield event.plain_result("当前群未创建牌局！请使用 /hj create 创建")
            return
            
        room = self.game_rooms[group_id]
        if room["status"] != "waiting":
            yield event.plain_result("牌局已经开始，无法添加机器人！")
            return
            
        if len(room["players"]) >= 4:
            yield event.plain_result("房间已满！")
            return
            
        # 生成机器人ID（使用负数以区分真实玩家）
        bot_id = f"bot_{len([p for p in room['players'] if str(p).startswith('bot_')])}"
        if bot_id in room["players"]:
            yield event.plain_result("该机器人已在牌局中！")
            return
            
        room["players"].add(bot_id)
        room["is_bot"] = {**room.get("is_bot", {}), bot_id: True}  # 标记机器人玩家
        
        # 为机器人分配一个名字
        bot_index = len([p for p in room["players"] if str(p).startswith("bot_")]) - 1
        bot_name = self.bot_names[bot_index % len(self.bot_names)]
        room["bot_names"] = {**room.get("bot_names", {}), bot_id: bot_name}
        
        yield event.plain_result(f"机器人 {bot_name} 加入成功！当前玩家数: {len(room['players'])}/4")
        
        if len(room["players"]) >= 2:
            yield event.plain_result("人数已达2人，可以使用 /hj start 开始游戏")

    @huanju.command("start")
    async def start_game(self, event: AstrMessageEvent):
        '''开始游戏'''
        group_id = event.message_obj.group_id
        if not group_id or group_id not in self.game_rooms:
            yield event.plain_result("当前群没有创建的牌局！")
            return
            
        room = self.game_rooms[group_id]
        if room["status"] != "waiting":
            yield event.plain_result("游戏已经开始！")
            return
            
        if len(room["players"]) < 2:
            yield event.plain_result("人数不足，至少需要2人才能开始游戏！")
            return
            
        if event.get_sender_id() != room["creator"]:
            yield event.plain_result("只有房主才能开始游戏！")
            return
            
        # 初始化游戏
        room["status"] = "playing"
        room["current_cards"] = {player_id: [] for player_id in room["players"]}
        room["player_status"] = {player_id: "playing" for player_id in room["players"]}
        room["points"] = {player_id: 0 for player_id in room["players"]}
        
        # 生成一副牌
        deck = []
        for suit in self.suits:
            for card in self.cards:
                deck.append(f"{suit}{card}")
        random.shuffle(deck)
        room["deck"] = deck
        
        # 每人发两张牌
        for player_id in room["players"]:
            for _ in range(2):
                card = self.draw_card(room)
                room["current_cards"][player_id].append(card)
            points = self.calculate_points(room["current_cards"][player_id])
            room["points"][player_id] = points
            
            cards_str = " ".join(room["current_cards"][player_id])
            result = MessageChain()
            result.message(f"@{player_id}\n你的手牌是: {cards_str}\n当前点数: {points}")
            await self.context.send_message(event.unified_msg_origin, result)
        
        # 设置第一个玩家
        room["current_player"] = list(room["players"])[0]
        first_player = room["current_player"]
        if str(first_player).startswith("bot_"):
            msg = MessageChain().message(f"游戏开始！轮到 {room['bot_names'][first_player]} 的回合")
            await self.context.send_message(event.unified_msg_origin, msg)
            await self.bot_play(event, group_id, first_player)
        else:
            yield event.plain_result(f"游戏开始！请 @{first_player} 选择 /hj hit 要牌 或 /hj stand 停牌")

    @huanju.command("hit")
    async def hit(self, event: AstrMessageEvent):
        '''要牌'''
        group_id = event.message_obj.group_id
        if not group_id or group_id not in self.game_rooms:
            yield event.plain_result("当前群没有进行中的牌局！")
            return
            
        room = self.game_rooms[group_id]
        player_id = event.get_sender_id()
        
        if room["status"] != "playing" or player_id != room["current_player"]:
            yield event.plain_result("还没轮到你的回合！")
            return
            
        if room["player_status"].get(player_id) == "stand":
            yield event.plain_result("你已经选择停牌了！")
            return
            
        # 发一张牌
        card = self.draw_card(room)
        room["current_cards"][player_id].append(card)
        points = self.calculate_points(room["current_cards"][player_id])
        room["points"][player_id] = points
        
        cards_str = " ".join(room["current_cards"][player_id])
        result = MessageChain()
        result.message(f"@{player_id}\n你要了一张牌: {card}\n当前手牌: {cards_str}\n当前点数: {points}")
        await self.context.send_message(event.unified_msg_origin, result)
        
        if points > 21:
            room["player_status"][player_id] = "bust"
            yield event.plain_result(f"爆牌了！")
            # 找下一个玩家
            players = list(room["players"])
            current_index = players.index(player_id)
            
            # 找下一个未停牌的玩家
            next_player = None
            for i in range(1, len(players)):
                index = (current_index + i) % len(players)
                if room["player_status"][players[index]] == "playing":
                    next_player = players[index]
                    break
            
            if next_player:
                room["current_player"] = next_player
                if str(next_player).startswith("bot_"):
                    msg = MessageChain().message(f"轮到 {room['bot_names'][next_player]} 的回合")
                    await self.context.send_message(event.unified_msg_origin, msg)
                    await self.bot_play(event, group_id, next_player)
                else:
                    yield event.plain_result(f"轮到 @{next_player} 的回合，请选择 /hj hit 要牌 或 /hj stand 停牌")
            else:
                # 游戏结束，计算结果
                result = await self.get_game_result(room)
                yield event.plain_result(result)
                del self.game_rooms[group_id]
        else:
            yield event.plain_result(f"请选择 /hj hit 继续要牌 或 /hj stand 停牌")

    @huanju.command("stand")
    async def stand(self, event: AstrMessageEvent):
        '''停牌'''
        group_id = event.message_obj.group_id
        if not group_id or group_id not in self.game_rooms:
            yield event.plain_result("当前群没有进行中的牌局！")
            return
            
        room = self.game_rooms[group_id]
        player_id = event.get_sender_id()
        
        if room["status"] != "playing" or player_id != room["current_player"]:
            yield event.plain_result("还没轮到你的回合！")
            return
            
        room["player_status"][player_id] = "stand"
        points = room["points"][player_id]
        yield event.plain_result(f"你选择停牌，最终点数: {points}")
        
        # 找下一个玩家
        players = list(room["players"])
        current_index = players.index(player_id)
        
        # 找下一个未停牌的玩家
        next_player = None
        for i in range(1, len(players)):
            index = (current_index + i) % len(players)
            if room["player_status"][players[index]] == "playing":
                next_player = players[index]
                break
        
        if next_player:
            room["current_player"] = next_player
            if str(next_player).startswith("bot_"):
                msg = MessageChain().message(f"轮到 {room['bot_names'][next_player]} 的回合")
                await self.context.send_message(event.unified_msg_origin, msg)
                await self.bot_play(event, group_id, next_player)
            else:
                yield event.plain_result(f"轮到 @{next_player} 的回合，请选择 /hj hit 要牌 或 /hj stand 停牌")
        else:
            # 游戏结束，计算结果
            result = await self.get_game_result(room)
            yield event.plain_result(result)
            del self.game_rooms[group_id]

    def draw_card(self, room: Dict) -> str:
        '''抽一张牌'''
        return room["deck"].pop()

    def calculate_points(self, cards: List[str]) -> int:
        '''计算点数'''
        points = 0
        ace_count = 0
        
        for card in cards:
            value = card[1:]  # 去掉花色
            if value in ['J', 'Q', 'K']:
                points += 10
            elif value == 'A':
                ace_count += 1
            else:
                points += int(value)
        
        # 处理A的点数
        for _ in range(ace_count):
            if points + 11 <= 21:
                points += 11
            else:
                points += 1
                
        return points

    async def bot_play(self, event: AstrMessageEvent, group_id: str, bot_id: str):
        '''机器人玩家的决策'''
        room = self.game_rooms[group_id]
        points = room["points"][bot_id]
        bot_name = room["bot_names"][bot_id]
        
        # 简单的AI策略：
        # 1. 点数小于等于11时，一定要牌
        # 2. 点数在12-16之间，70%概率要牌
        # 3. 点数大于等于17时，停牌
        if points <= 11:
            should_hit = True
        elif points >= 17:
            should_hit = False
        else:
            should_hit = random.random() < 0.7
            
        # 添加延迟，模拟思考时间
        await asyncio.sleep(random.uniform(1, 2))
            
        if should_hit:
            # 要牌
            card = self.draw_card(room)
            room["current_cards"][bot_id].append(card)
            new_points = self.calculate_points(room["current_cards"][bot_id])
            room["points"][bot_id] = new_points
            
            cards_str = " ".join(room["current_cards"][bot_id])
            # 使用 Bot 发送消息
            msg = MessageChain().message(f"{bot_name} 选择要牌\n抽到了: {card}\n当前手牌: {cards_str}\n当前点数: {new_points}")
            await self.context.send_message(event.unified_msg_origin, msg)
            
            if new_points > 21:
                room["player_status"][bot_id] = "bust"
                msg = MessageChain().message(f"{bot_name} 爆牌了！")
                await self.context.send_message(event.unified_msg_origin, msg)
                await self.next_turn(event, group_id, bot_id)
            else:
                # 机器人继续决策
                await self.bot_play(event, group_id, bot_id)
        else:
            # 停牌
            room["player_status"][bot_id] = "stand"
            msg = MessageChain().message(f"{bot_name} 选择停牌，最终点数: {points}")
            await self.context.send_message(event.unified_msg_origin, msg)
            await self.next_turn(event, group_id, bot_id)

    async def next_turn(self, event: AstrMessageEvent, group_id: str, current_player: str):
        '''处理下一个玩家的回合'''
        room = self.game_rooms[group_id]
        players = list(room["players"])
        current_index = players.index(current_player)
        
        # 找下一个未停牌的玩家
        next_player = None
        for i in range(1, len(players)):
            index = (current_index + i) % len(players)
            if room["player_status"][players[index]] == "playing":
                next_player = players[index]
                break
        
        if next_player:
            room["current_player"] = next_player
            if str(next_player).startswith("bot_"):
                # 如果下一个是机器人，自动进行操作
                bot_name = room["bot_names"][next_player]
                msg = MessageChain().message(f"轮到 {bot_name} 的回合")
                await self.context.send_message(event.unified_msg_origin, msg)
                await self.bot_play(event, group_id, next_player)
            else:
                msg = MessageChain().message(f"轮到 @{next_player} 的回合，请选择 /hj hit 要牌 或 /hj stand 停牌")
                await self.context.send_message(event.unified_msg_origin, msg)
        else:
            # 游戏结束，计算结果
            result = await self.get_game_result(room)
            msg = MessageChain().message(result)
            await self.context.send_message(event.unified_msg_origin, msg)
            del self.game_rooms[group_id]

    async def get_game_result(self, room: Dict) -> str:
        '''获取游戏结果'''
        # 找出未爆牌的最大点数
        max_points = 0
        winners = []
        for player_id, status in room["player_status"].items():
            points = room["points"][player_id]
            if status != "bust" and points <= 21:
                if points > max_points:
                    max_points = points
                    winners = [player_id]
                elif points == max_points:
                    winners.append(player_id)
        
        # 生成结果字符串
        result = "游戏结束！\n"
        for player_id in room["players"]:
            cards_str = " ".join(room["current_cards"][player_id])
            status = "爆牌" if room["player_status"][player_id] == "bust" else f"{room['points'][player_id]}点"
            # 显示机器人名字
            display_name = room["bot_names"][player_id] if str(player_id).startswith("bot_") else player_id
            result += f"{display_name}: {cards_str} ({status})\n"
        
        if winners:
            winner_names = [room["bot_names"][w] if str(w).startswith("bot_") else w for w in winners]
            result += f"\n获胜者: {', '.join(winner_names)} ({max_points}点)"
        else:
            result += "\n所有人都爆牌了！"
            
        return result

    @huanju.command("help")
    async def show_help(self, event: AstrMessageEvent):
        '''显示帮助信息'''
        help_text = """欢乐21点指令说明：
/hj create - 创建游戏房间
/hj join - 加入游戏
/hj addbot - 添加机器人玩家
/hj start - 开始游戏（仅房主可用）
/hj hit - 要牌
/hj stand - 停牌
/hj quit - 退出游戏
/hj help - 显示本帮助信息

游戏规则：
1. 2-4人即可开始游戏
2. A可以算1点或11点
3. JQK都算10点
4. 其他牌按面值计算
5. 超过21点爆牌
6. 未爆牌者中点数最大者获胜
7. 可以添加机器人玩家凑人数
"""
        yield event.plain_result(help_text)
