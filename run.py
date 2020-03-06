#!/usr/bin/env python

from collections import namedtuple
from datetime import datetime
import os, sys
import xml.etree.ElementTree as ET
import logging

import requests
import re
import twitter

log = logging.getLogger()
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
fhandler = logging.FileHandler(filename='twitter.log', mode='a')
fhandler.setFormatter(formatter)
log.addHandler(fhandler)
log.setLevel(logging.INFO)

CONFIG = [
    {
        'id': 'CSCL',
        'name': 'Computation and Language',
        'url': 'http://export.arxiv.org/rss/cs.CL'
    }
    # Human Computer Interaction
    # ('CSHC', 'http://export.arxiv.org/rss/cs.HC'),
]

CONSUMER_KEY = 'a'
CONSUMER_SECRET = 'a'
ACCESS_TOKEN_KEY = 'a'
ACCESS_TOKEN_SECRET = 'a'

def parse_articles(xml):
    """
    For the given string of arXiv.org RSS XML, return list of Articles
    """
    root = ET.ElementTree(ET.fromstring(xml))
    ns = {'rss': 'http://purl.org/rss/1.0/'}
    items = root.findall('rss:item', ns)
    return [
        [
            item.find('rss:{}'.format(field), ns).text
            for field in ['title', 'link', 'description']
        ] for item in items
    ]

def generate_tweet(article):
    """
    Construct a tweet for the given article
    """
    MAX_CHAR = 240
    
    # Take the proper title
    title = article[0].split('. (arXiv')[0]
    # Twitter links are 23 characters
    linkPlaceholder = '#'*23
    link = article[1]
    # Abstract
    abstract = article[2]

    out = f'{title} {linkPlaceholder} {abstract}'    
    out = out[:MAX_CHAR]
    out = out.replace(linkPlaceholder, link)

    out = re.sub(r'<.*?>', ' ', out)
    out = re.sub(r'\n+', ' ', out)
    out = re.sub(r'\s+', ' ', out)

    # Go back and remove everything after the last end of word/phrase/sentence
    out = re.sub(r'(\.|\,|\?|\s)[^\.\,\?\s]*$', r'-', out)
    while len(out) > MAX_CHAR:
        out = re.sub(r'(\.|\,|\?|\s)[^\.\,\?\s]*$', r'-', out)
    
    return out


def send_tweet(api, tweet):
    """
    Actually POST tweet to twitter API
    """
    try:
        api.PostUpdate(tweet)
        log.info(f'Sent "{tweet}"')
    except twitter.TwitterError as e:
        log.warning(f'Failed to send "{tweet}" ({e.message})')

if __name__ == '__main__':
    log.info('Running run.py on {}'.format(datetime.now()))

    for source in CONFIG:
        res = requests.get(source['url'])
        if not res.ok:
            log.warning(f'Failed on {source["url"]}: {res.reason}')
            continue

        api = twitter.Api(
            CONSUMER_KEY,
            CONSUMER_SECRET,
            access_token_key=ACCESS_TOKEN_KEY,
            access_token_secret=ACCESS_TOKEN_SECRET
        )

        for article in parse_articles(res.text):
            print(generate_tweet(article))
            send_tweet(api, generate_tweet(article))