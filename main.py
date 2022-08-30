import logging
import os
import sys
from datetime import datetime, timedelta
import json
import argparse
from slack_sdk import WebClient

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("Stats")
no_days = 30


def start_time() -> float:
    old = datetime.today() - timedelta(days=no_days)
    return old.timestamp()


class Channel:
    def __init__(self, channel_name: str, icon: str, post_message: bool):
        self.channel_name = channel_name
        self.icon = icon
        self.post_message = post_message


class UserStat:
    def __init__(self, user_id: str, user_name: str, count: int):
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
    Channel('android-talks', ':android:', post_message=True),
    Channel('ios-talks', ':apple:', post_message=True),
    Channel('flutter-talks', ':flutter:', post_message=True),
    Channel('frontend-talks', ':spider_web:', post_message=True),
    Channel('elixir-talks', ':cloud:', post_message=False),
]


class SlackStatsCalculator:
    def __init__(self, client: WebClient, dry_run: bool):
        self.client = client
        self.dry_run = dry_run

    def _find_conversation_id(self, channel_name: str) -> str:
        for result in self.client.conversations_list():
            for channel in result["channels"]:
                if channel["name"] == channel_name:
                    return channel["id"]
        raise Exception(f"Not found conversation {channel_name}")

    def _user_stats(self, stats: Stats) -> list[UserStat]:
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

    def _retrieve_messages(self, channel_id: str, oldest: float) -> Stats:
        stats = Stats()
        for result in self.client.conversations_history(channel=channel_id, oldest=str(oldest)):
            conversation_history = result["messages"]

            for message in conversation_history:
                if "subtype" in message or "bot_id" in message:
                    logger.debug(f"Skipping message: {message['text']}: {json.dumps(message)}")
                else:
                    logger.debug(f"Counting message: {message['text']}: {json.dumps(message)}")
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

    def prepare_message(self, root_channel: str, channels_stats: list[ChannelStats]) -> str:
        def format_chanel_stats(channel: ChannelStats):
            return f"{channel.channel.icon} {channel.stats.questions} tematów, {channel.stats.reactions} emoji, i aż {channel.stats.replays} wiadomości"

        channel_stat = next(
            channel_stat for channel_stat in channels_stats if channel_stat.channel.channel_name == root_channel)
        others_stats = "\n".join(
            [f"- {format_chanel_stats(x)}" for x in channels_stats if x.channel.channel_name != root_channel])

        message = "\n".join(
            [f" - <@{user.user_id}> ({user.count} :heavy_multiplication_x::memo:)" for user in
             channel_stat.user_stats[:3]])
        return f"""
<!here> *Poniżej :postbox: podsumowanie ostatnich {no_days} dni :calendar::*

Tym razem:
- {format_chanel_stats(channel_stat)}
Dla porównania nasi bracia spłodzili:
{others_stats}

Na {channel_stat.channel.icon} najwięcej napisali:
{message}

_Pamiętajcie, by pisać :writing_hand::skin-tone-5: i dodawać emoji :upside_down_face: pod wiadomościami by piszący nie czuli się samotni :alien:!_
"""

    def _get_stats(self, channel: Channel, oldest: float) -> ChannelStats:
        conversation_id = self._find_conversation_id(channel.channel_name)
        logger.info(f"Found conversation ID: {conversation_id}")
        stats = self._retrieve_messages(conversation_id, oldest)
        user_stats = self._user_stats(stats)
        return ChannelStats(channel, stats, user_stats)

    def get_stats(self) -> list[ChannelStats]:
        oldest = start_time()
        logger.info(f"start: {oldest}")
        channels_stats = [self._get_stats(channel, oldest) for channel in all_channels]
        return channels_stats

    def post(self, root_channel: str, channels_stats: list[ChannelStats]) -> None:
        message = self.prepare_message(root_channel, channels_stats)
        logger.info(message)
        if not self.dry_run:
            message_channel = self._find_conversation_id(root_channel)
            # overwrite channel for testing
            # message_channel = 'GCQ4KBS11'
            self.client.chat_postMessage(channel=message_channel, text=message)

    def calculate(self) -> None:
        channels_stats = self.get_stats()
        for channel in all_channels:
            if channel.post_message:
                self.post(channel.channel_name, channels_stats)


def do_action():
    parser = argparse.ArgumentParser(description='Process stats')
    parser.add_argument('--dry-run', dest='dry_run', action='store_const',
                        const=True, default=False,
                        help='Set the dry run, without posting')
    args = parser.parse_args()
    auth_token = os.environ.get('SLACK_BOT_TOKEN')
    if not auth_token:
        sys.stderr.write('You need to provide SLACK_BOT_TOKEN environment variable\n')
        sys.exit(1)
    client = WebClient(token=auth_token)
    calculator = SlackStatsCalculator(client, args.dry_run)
    calculator.calculate()


if __name__ == '__main__':
    do_action()
