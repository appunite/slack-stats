import logging
import os
from datetime import datetime, timedelta
import json

no_days = 30


def start_time():
    old = datetime.today() - timedelta(days=no_days)
    return old.timestamp()


logging.basicConfig(level=logging.DEBUG)
from slack_sdk import WebClient

logger = logging.getLogger("Stats")


class Channel:
    def __init__(self, channel_name, icon):
        self.channel_name = channel_name
        self.icon = icon


class UserStat:
    def __init__(self, user_id, user_name, count):
        self.user_id = user_id
        self.user_name = user_name
        self.count = count


class Stats:
    def __init__(self):
        self.questions = 0
        self.active_users = {}
        self.replays = 0
        self.reactions = 0

    def add_message(self, user_id):
        if user_id in self.active_users:
            self.active_users[user_id] += 1
        else:
            self.active_users[user_id] = 1

    def add_messages(self, user_ids):
        for user_id in user_ids:
            self.add_message(user_id)


class ChannelStats:
    def __init__(self, channel: Channel, stats: Stats, user_stats: list[UserStat]):
        self.channel = channel
        self.stats = stats
        self.user_stats = user_stats


all_channels = [
    Channel('android-talks', ':android:'),
    Channel('ios-talks', ':apple:'),
    Channel('flutter-talks', ':flutter:'),
    Channel('frontend-talks', ':spider_web:')
]


class Xyz:
    def __init__(self, client):
        self.client = client

    def _find_conversation_id(self, channel_name):
        for result in self.client.conversations_list():
            for channel in result["channels"]:
                if channel["name"] == channel_name:
                    return channel["id"]
        raise Exception(f"Not found conversation {channel_name}")

    def _user_stats(self, stats : Stats) -> list[UserStat]:
        users = stats.active_users.items()
        users = sorted(users, key=lambda user: user[1], reverse=True)
        result = []
        for user in users:
            (user_id, count) = user
            if user_id == "USLACKBOT":
                logger.debug(f"Skipping slackbot")
                continue
            user = self.client.users_info(user=user_id)["user"]
            if user["is_bot"]:
                logger.debug(f"Skipping bot user: {json.dumps(user)}, messages: {count}")
                continue
            name = user["real_name"]
            result.append(UserStat(user_id, name, count))
        return result

    def _retrieve_messages(self, channel_id, oldest) -> Stats:
        stats = Stats()
        for result in self.client.conversations_history(channel=channel_id, oldest=oldest):
            conversation_history = result["messages"]

            for message in conversation_history:
                if "subtype" in message:
                    logger.debug(f"Skipping message: {json.dumps(message)}")
                    continue
                logger.debug(f"Counting message: {json.dumps(message)}")
                stats.questions += 1
                stats.add_message(message["user"])
                if "reply_users" in message:
                    stats.add_messages(message["reply_users"])
                if "reply_count" in message:
                    stats.replays += message["reply_count"]
                if "reactions" in message:
                    reactions = message["reactions"]
                    for reaction in reactions:
                        stats.reactions += reaction["count"]
        return stats

    def prepare_message(self, root_channel: str) -> str:
        oldest = start_time()
        logger.info(f"start: {oldest}")

        def format_chanel_stats(channel: ChannelStats):
            return f"{channel.channel.icon} {channel.stats.questions} tematów, {channel.stats.reactions} emoji, i aż {channel.stats.replays} wiadomości"

        channels_stats = [self._get_stats(channel, oldest) for channel in all_channels]

        channel_stat = next(
            channel_stat for channel_stat in channels_stats if channel_stat.channel.channel_name == root_channel)
        others_stats = "\n".join(
            [f"- {format_chanel_stats(x)}" for x in channels_stats if x.channel.channel_name != root_channel])

        message = "\n".join(
            [f" - <@{user.user_id}> ({user.count} :heavy_multiplication_x::memo:)" for user in channel_stat.user_stats[:3]])
        return f"""
<!here> *Poniżej :postbox: podsumowanie ostatnich {no_days} dni :calendar::*

Tym razem:
- {format_chanel_stats(channel_stat)}
Dla porównania nasi bracia spłodzili:
{others_stats}

Na :android: najwięcej napisali:
{message}

_Pamiętajcie, by pisać :writing_hand::skin-tone-5: i dodawać emoji :upside_down_face: pod wiadomościami by piszący nie czuli się samotni :alien:!_
"""

    def _get_stats(self, channel: Channel, oldest):
        conversation_id = self._find_conversation_id(channel.channel_name)
        logger.info(f"Found conversation ID: {conversation_id}")
        stats = self._retrieve_messages(conversation_id, oldest)
        user_stats = self._user_stats(stats)
        return ChannelStats(channel, stats, user_stats)

    def post(self, root_channel):
        message_channel = self._find_conversation_id(root_channel)
        # overwrite channel for testing
        # message_channel = 'GCQ4KBS11'
        message = self.prepare_message(root_channel)
        logger.info(message)
        self.client.chat_postMessage(channel=message_channel, text=message)

    def do_action(self):
        self.post('ios-talks')
        self.post('flutter-talks')
        self.post('android-talks')
        self.post('frontend-talks')


def do_action():
    client = WebClient(token=os.environ.get('SLACK_BOT_TOKEN'))
    action = Xyz(client)
    action.do_action()


if __name__ == '__main__':
    do_action()
