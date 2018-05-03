import requests
import json
import datetime
import time
import os
import sqlite3
from random import randint
from time import sleep

try:
    from terminaltables import AsciiTable
    PRINT_TABLE = True
except ImportError as e:
    PRINT_TABLE = False


class Stories():
    def __init__(self, element=None):
        """
        Initialize the Stories, either as empty Obj or from a dictionary repr.
        Args:
            element: Instagram-provided dictionary with informations.
        """
        self.media_id, self.user_id, self.nickname, self.fullname = "", "", "", ""
        self.media_type, self.timestamp = 0, 0
        self.url, self.caption = "", ""
        self.mentions, self.locations, self.hashtags, self.ctas = [], [], [], []

        if element:  # If we provide the Instagram object we use that to retrieve the data
            media_id = element['id']
            self.media_id = media_id
            ## - Usr - <>
            self.user_id = element['user']['pk']
            self.nickname = element["user"]["username"]
            self.fullname = element["user"]["full_name"]
            ## - Video/Pic - <>
            self.media_type = element['media_type']
            if element['media_type'] == 2:
                videos = element['video_versions']
                video_url = videos[0]['url']
                self.url = video_url
            if element['media_type'] == 1:
                pics = element['image_versions2']['candidates']
                pic_url = pics[0]['url']
                self.url = pic_url
            ## - Time - <>
            time = element['taken_at']
            self.timestamp = datetime.datetime.fromtimestamp(time).strftime('%Y-%m-%d %H:%M:%S')
            ## - Caption - <>
            caption = element['caption']  
            if caption:
                self.caption = caption['text']
            ## - Someone else tagged - <>
            if 'reel_mentions' in element:
                mentions = element['reel_mentions']
                if mentions:
                    for idx, mention in enumerate(mentions):
                        self.mentions.append(
                            (mention['user']['pk'], mention['user']['username'], mention['user']['full_name']))
            ## - GeoTag - <> 
            if 'story_locations' in element:
                geotags = element['story_locations']
                if geotags:
                    for geotag in geotags:
                        loc = geotag['location']
                        if 'name' in loc and 'lat' in loc and 'lng' in loc and 'pk' in loc:  # Quite edge case..
                            self.locations.append((loc['name'], loc['lat'], loc['lng'], loc['pk']))
            ## Hashtag
            if 'story_hashtags' in element:
                hashtags = element['story_hashtags']
                if hashtags:
                    for hashtag in hashtags:
                        self.hashtags.append(hashtag['hashtag']['name'])
            ## CTA
            if 'story_cta' in element:
                for typ in element['story_cta']:
                    if 'links' in typ:
                        for idx, cta in enumerate(typ['links']):
                            self.ctas.append(cta['webUri'])

    def __str__(self):
        """ Return a Human-Readable representation of the Object"""
        return "{} | USR ID {} NK {} - FN {} - Type: {}".format(self.media_id, self.user_id, self.nickname,
                                                                self.fullname,
                                                                "VIDEO" if self.media_type == 2 else "PIC")

    def from_json(self, d):
        """ Setup the object using a Json-able string """
        self.__dict__ = json.load(d)

    def print_info(self):
        """ Human friendly visualization of the data saved in Stories """
        print("\n-----------\n")
        print("ID: " + self.media_id)
        print("USR ID {} NK {} - FN {}".format(self.user_id, self.nickname, self.fullname))

        if self.media_type == 2:
            print("Video URL:\n{}".format(self.url))
        else:
            print("Photo URL:\n{}".format(self.url))
        print("TIMESTAMP:\n" + self.timestamp)
        #
        if self.caption:
            print("CAPTIONS:")
            for quote in self.caption.splitlines():    print(quote, end='\t')
            print("")
        #
        if self.mentions:
            print("MENZIONI:")
            for idx, mention in enumerate(self.mentions):
                print("{} - USR ID {} NK {} - FN {}".format(idx + 1, mention[0], mention[1], mention[2]))
        #
        if self.locations:
            print("GEOTAGGED:")
            for geotag in self.locations:
                print("NAME: = {}\nLAT: = {}\nLNG: = {}".format(str(geotag[0]), str(geotag[1]), str(geotag[2])))
        #
        if self.hashtags:
            print("HASHTAGS:")
            for hashtag in self.hashtags:    print("# : " + hashtag)
        #
        if self.ctas:
            print("CTA:")
            for idx, cta in enumerate(self.ctas):    print("{} | Link: {}".format(idx + 1, cta))

    def discovered(self):
        """
        Provides the mentions found in this Story
        Returns: List of tuples, eventually empty, with the pair Source-Discovered of User ID
        """
        return [(self.user_id, mention[0]) for mention in self.mentions] if self.mentions else []


class InstagramStories():
    def __init__(self):
        """ Initialize Options """
        self.location_id = {}
        self.counter = 0
        self.basefolder, self.db_path = os.path.join("_", "_"), "_"
        self.db_seen = "_"
        self.degree_path = "_"
        self.mode = 0
        self.res = []
        self.DELAY_REQUESTS, self.VERBOSE = True, False

    def set_mode(self, mode_n):
        """
        Setter for current operating mode
        Args:
            mode_n:  Int for the respective mode
        """
        self.mode = mode_n

    def tray_to_ids(self):
        """
        Obtains from the Stories Tray the followed account IDs
        Returns: List of Instagram account IDs
        """
        tray_endpoint = "https://i.instagram.com/api/v1/feed/reels_tray/"
        r = requests.get(tray_endpoint, headers=self.cookie)
        stories = r.json()
        usr = []
        ids = []
        for element in stories['tray']:
            ids.append(element['id'])
            username = element['user']['username']
            usr.append(username)
        if PRINT_TABLE:  # Toggleable option to print the table
            self.print_ids_table(usr, ids)
        return ids

    @staticmethod
    def print_ids_table(usr, ids):
        """ Nicely print the table of Username - IDs collected """
        table_data = [[x, y] for x, y in zip(usr, ids)]
        table_data = [("Username", "ID")] + table_data
        table = AsciiTable(table_data)
        print(table.table)

    def get_id_location(self, location_name):
        """
        Call location_stories function after retrieving the best candidate for the place IDs.
        Support a dict-like cache for avoiding multiple unneeded queries
        Args:
            location_name (str): Geographical places
        """
        if location_name not in self.location_id:
            location_endpoint = "https://i.instagram.com/api/v1/fbsearch/places/?query={}/".format(location_name)
            r = requests.get(location_endpoint, headers=self.cookie)
            d = r.json()
            place_id = d['items'][0]['location']['pk']
            print("{} - {}".format(location_name, place_id))
            self.location_id[location_name] = place_id
        self.location_stories(self.location_id[location_name])
    
    def user_from_id(self, user_id):
        """
        Retrieve information of a user from it's ID
        Args:
            user_id (int): ID of person of interest
        """
        user_endpoint = "https://i.instagram.com/api/v1/users/{}/info/".format(user_id)
        r = requests.get(user_endpoint, headers = self.cookie)
        d = r.json()
        
        username, fullname = d['user']['username'], d['user']['full_name']
        followers, followed = d['user']['follower_count'], d['user']['following_count']
        
        return (username, fullname, followers, followed)
        
    def location_stories(self, location_id):
        """
        Retrieve the location_id Stories and process them.
        Args:
            location_id (int): ID of location of interest
        """
        location_endpoint = "https://i.instagram.com/api/v1/feed/location/{}/".format(location_id)
        r = requests.get(location_endpoint, headers=self.cookie)
        d = r.json()
        self.analytics_story(d['story']['items'])

    def location_people(self, locations):
        """
        Retrieve geo-tagged stories of a location and store relevant information in a database
        Args:
            locations_id (int): ID of location of interest
        """
        db = sqlite3.connect(self.db_path)
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users(timestamp TEXT, placename TEXT, lat TEXT, lng TEXT, user_id TEXT, nickname TEXT, fullname TEXT, city_id TEXT, city_name TEXT, PRIMARY KEY (timestamp, user_id))
        ''')
        db.commit()
        for location_tuple in locations:

            if self.DELAY_REQUESTS: sleep(randint(800, 1700) / 1000)  # Wait between 0.8 and 1.7 second

            location, loc_name = location_tuple
            print("- LOCATION: {} -".format(loc_name))

            location_endpoint = "https://i.instagram.com/api/v1/feed/location/{}/".format(location)
            r = requests.get(location_endpoint, headers=self.cookie)
            d = r.json()
            if 'story' in d:
                stories = d['story']['items']
                for story in stories:
                    curr = Stories(story)
                    if curr.locations:
                        geotag = curr.locations[0]
                        if geotag:
                            name, lat, lng = geotag[0], geotag[1], geotag[2]
                            print("TIME: {} | {} : LAT: {} LNG: {} | ID {} NK {} - FN {}".format(curr.timestamp, name,
                                                                                                 lat, lng, curr.user_id,
                                                                                                 curr.nickname,
                                                                                                 curr.fullname))
                            cursor.execute('''
                                INSERT OR IGNORE INTO users(timestamp, placename, lat, lng, user_id, nickname, fullname, city_id, city_name) VALUES(?,?,?,?,?,?,?,?,?)''',
                                           (curr.timestamp, name, lat, lng, curr.user_id, curr.nickname, curr.fullname,
                                            geotag[3], loc_name))
                db.commit()
            else:
                print(d) # Edge cases where we are unable to retrieve information

    def users_stories(self, arr_ids):
        """
        Obtain Stories from multiple users. Support for randomly delayed requests
        Args:
            arr_ids: List of IDs of user we want to retrieve
        Returns:
            self.res: List of Stories elements obtained
        """
        self.counter = 0
        userid_endpoint = "https://i.instagram.com/api/v1/feed/user/{}/reel_media/"
        for idx, ids in enumerate(arr_ids):

            if self.DELAY_REQUESTS: sleep(randint(800, 1700) / 1000)  # Wait between 0.8 and 1.7 second

            url = userid_endpoint.format(ids)
            r = requests.get(url, headers=self.cookie)
            d = r.json()
            if 'items' in d and d['items']:
                items = d['items']
                username = items[0]['user']['username']
                print("\n\n___________________________________")
                print("{}/{} Username: -| {} |-".format(idx + 1, len(arr_ids), username))
                print("___________________________________")
                self.analytics_story(items)
            else:
                print("Empty stories for url {}".format(url))
                continue
        print("\n\nWe finished processing {} users with {} stories".format(len(arr_ids), self.counter))
        return self.res

    def analytics_story(self, usr_stories):
        """
        Convert Instagram JSON response for a User into Stories objects
        Args:
            usr_stories: dict of users stories
        """
        for element in usr_stories:  # Iter all user stories
            curr_s = Stories(element)  # Create a custom class istance to hold the relevant information
            self.counter += 1  # Counter to keep track of number of processed stories
            if self.VERBOSE: curr_s.print_info()  # Nicely print all the information
            self.res.append(curr_s)

    @staticmethod
    def save_stories_json(stories, path):
        with open(path, 'w+') as f_out:
            json.dump(stories.__dict__, f_out)

    @staticmethod
    def load_stories_json(path):
        new_user = Stories()
        with open(path, 'r') as f_in:
            new_user.from_json(f_in)
        new_user.print_info()
        return new_user

    def save_stories(self, stories):
        """
        Given Stories object proceed to save them as .json files using a database to check if they are already saved
        Args:
            stories: List of Stories object
        """
        skipped = 0
        date = datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
        path = os.path.join(self.basefolder, date + ".json")
        with open(path, 'w+') as f:
            to_save = []
            db = sqlite3.connect(self.db_seen)
            cursor = db.cursor()
            cursor.execute('''
                    CREATE TABLE IF NOT EXISTS seen(media_id TEXT PRIMARY KEY)
                ''')
            db.commit()
            for story in stories:
                cursor.execute("SELECT * FROM seen WHERE media_id = ?", (story.media_id,))
                ex = cursor.fetchone()
                if ex:
                    skipped += 1
                    continue
                else:
                    to_save.append(story.__dict__)
                    cursor.execute('''INSERT OR IGNORE INTO seen(media_id) VALUES(?)''', (str(story.media_id),))
            print("We skipped {} stories".format(skipped))
            json.dump(to_save, f)
            db.commit()

    def degree_separation(self, grade, seeds):
        """
        Proceed to gradually discover Instagram users from already visited        
        Args:
            grade (int): Eventually initialize the database with the Seeds 
            seeds: List of seeds to start the discovery from 
        """
        db = sqlite3.connect(self.degree_path)
        cursor = db.cursor()

        if grade == 0:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS degree(source TEXT, refered TEXT, PRIMARY KEY(source, refered))
            ''')
            db.commit()
            for seed in seeds:
                cursor.execute('''
                INSERT OR IGNORE INTO degree(source, refered) VALUES(?,?)''',
                               (seed, None))  
            db.commit()

        cursor.execute('''SELECT source, refered FROM degree''')
        rows = cursor.fetchall()
        check = set()
        for row in rows:
            check.add(row[0])
            check.add(row[1])
        if None in check:
            check.remove(None)

        self.users_stories(list(check))

        for story in self.res:
            curr = story.discovered()
            if curr:  # If we have at least a discovery....
                for pair in curr:  # Then for each discovery add the tuple to the db
                    cursor.execute('''INSERT OR IGNORE INTO degree(source, refered) VALUES(?,?)''',
                                   (str(pair[0]), str(pair[1])))
        db.commit()
