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


class Xyz:
    def __init__(self, client):
        self.client = client

    def _find_conversation_id(self, channel_name):
        for result in self.client.conversations_list():
            for channel in result["channels"]:
                if channel["name"] == channel_name:
                    return channel["id"]
        raise Exception(f"Not found conversation {channel_name}")

    def _user_stats(self, stats):
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

    def _retrieve_messages(self, channel_id, oldest):
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

    def prepare_message(self):
        oldest = start_time()
        logger.info(f"start: {oldest}")
        # return
        stats_android, user_stats_android = self._get_stats("android-talks", oldest)
        stats_ios, user_stats_ios = self._get_stats('ios-talks', oldest)
        stats_flutter, user_stats_flutter = self._get_stats('flutter', oldest)
        stats_web, user_stats_web = self._get_stats('web-frontend', oldest)
        message = "\n".join(
            [f" - <@{user.user_id}> ({user.count} :heavy_multiplication_x::memo:)" for user in user_stats_android[:3]])
        return f"""
<!here> *Poniżej :postbox: podsumowanie ostatnich {no_days} dni :calendar::*

Tym razem:
- :android: {stats_android.questions} tematów, {stats_android.reactions} emoji, i aż {stats_android.replays} wiadomości
Dla porównania nasi bracia spłodzili:
- :apple: {stats_ios.questions} tematów, {stats_ios.reactions} emoji, i aż {stats_ios.replays} wiadomości
- :flutter: {stats_flutter.questions} tematów, {stats_flutter.reactions} emoji, i aż {stats_flutter.replays} wiadomości
- :spider_web: {stats_web.questions} tematów, {stats_web.reactions} emoji, i aż {stats_web.replays} wiadomości

Na :android: najwięcej napisali:
{message}

_Pamiętajcie, by pisać :writing_hand::skin-tone-5: i dodawać emoji :upside_down_face: pod wiadomościami by piszący nie czuli się samotni :alien:!_
"""

    def _get_stats(self, channel_name, oldest):
        conversation_id = self._find_conversation_id(channel_name)
        logger.info(f"Found conversation ID: {conversation_id}")
        stats = self._retrieve_messages(conversation_id, oldest)
        user_stats = self._user_stats(stats)
        return stats, user_stats

    def do_action(self):
        # message_channel = "GCQ4KBS11"
        message_channel = self._find_conversation_id("android-talks")
        message = self.prepare_message()
        logger.info(message)
        self.client.chat_postMessage(channel=message_channel, text=message)


def do_action():
    client = WebClient(token=os.environ.get('SLACK_BOT_TOKEN'))
    action = Xyz(client)
    action.do_action()


if __name__ == '__main__':
    do_action()
