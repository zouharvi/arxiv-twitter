#!/usr/bin/env python3

from collections import namedtuple
from datetime import datetime
import os, sys, time
import xml.etree.ElementTree as ET
import logging
import yaml

import requests
import re
import twitter
import nltk

log = logging.getLogger()
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
fhandler = logging.FileHandler(filename='twitter.log', mode='a')
fhandler.setFormatter(formatter)
log.addHandler(fhandler)
log.setLevel(logging.INFO)

ARXIV_SRC = [
    {
        'id': 'CSCL',
        'name': 'Computation and Language',
        'url': 'http://export.arxiv.org/rss/cs.CL'
    }
]

TWEET_DELAY = 60*20
REFRESH_DELAY = 60*60*10
LINK_PLACEHOLER = '0'*23
AUTH_OBJ = None

def parse_articles(xml):
    """
    For the given string of arXiv.org RSS XML, return list of Articles
    """
    # XPath didn't work
    root = ET.ElementTree(ET.fromstring(xml))
    ns = {'rss': 'http://purl.org/rss/1.0/'}
    items = root.findall('rss:item', ns)
    date = re.search(r'<dc:date>(.*)</dc:date>', xml).groups()[0]
    return [
        date,
        [
            [
                item.find('rss:{}'.format(field), ns).text
                for field in ['title', 'link', 'description']
            ] for item in items
        ]
    ]

def is_hashtag_viable(word, tag):
    MIN_HASHTAGIFY = 10

    if '-' in word:
        return False
    if LINK_PLACEHOLER in word:
        return False
    if len(word) >= 3 and all([x.isupper() for x in word]):
        return True
    if len(word) >= 3 and sum([1 if x.isupper() else 0 for x in word]) >= 3:
        return True
    if len(word) >= MIN_HASHTAGIFY and (tag in ['NN', 'NNP', 'NNS', 'JJ']):
        return True

def add_hashtags(abstract):
    hashtags = set()
    tokens = nltk.word_tokenize(abstract)
    tags = nltk.pos_tag(tokens)
    for word, tag in tags:
        if is_hashtag_viable(word, tag):
            hashtags.add(word)

    for hashtag in hashtags:
        abSp = abstract.split(hashtag)
        # we add hashtags to the first word only
        abstract = abSp[0] + '#' + hashtag + hashtag.join(abSp[1:])
    
    return abstract

def generate_tweet(article):
    """
    Construct a tweet for the given article
    """
    MAX_CHAR = 240
    
    # Take the proper title
    title = article[0].split('. (arXiv')[0]
    link = article[1]
    # Abstract
    abstract = re.sub(r'\n+', ' ', article[2])

    out = f'{title}\n{LINK_PLACEHOLER}\n{abstract}'    
    out = add_hashtags(out)

    out = out[:MAX_CHAR]
    out = out.replace(LINK_PLACEHOLER, link)

    out = re.sub(r'<.*?>', '', out)
    out = re.sub(r'\n+', r'\n', out)
    out = re.sub(r'\ +', ' ', out)
    out = re.sub(r'\#+', '#', out)
    out = re.sub(r'(\w)\#', r'\1', out)
    
    out = out[:MAX_CHAR]

    # Go back and remove everything after the last end of word/phrase/sentence
    out = re.sub(r'(\.|\,|\?|\s)[^\.\,\?\s]*$', r'-', out)
    
    return out

def send_tweet(api, tweet):
    """
    Actually POST tweet to twitter API
    """
    tweet_clean = tweet.replace('\n', ' ')
    try:
        api.PostUpdate(tweet)
        log.info(f'Sent "{tweet_clean}"')
    except twitter.TwitterError as e:
        log.warning(f'Failed to send "{tweet_clean}" ({e.message})')

PREV_DATE = None

def parse_keys():
    global AUTH_OBJ
    with open('keys.yaml', 'r') as f:
        AUTH_OBJ = yaml.safe_load(f)
    

if __name__ == '__main__':
    log.info('Running run.py')
    parse_keys()

    while True:
        for source in ARXIV_SRC:
            res = requests.get(source['url'])
            if not res.ok:
                log.warning(f'Failed on {source["url"]}: {res.reason}')
                continue

            api = twitter.Api(
                AUTH_OBJ['consumer_key'],
                AUTH_OBJ['consumer_secret'],
                access_token_key=AUTH_OBJ['access_token_key'],
                access_token_secret=AUTH_OBJ['access_token_secret']
            )

            try:
                with open('prev_sent.time', 'r') as f:
                    pdate = f.readlines()[0].rstrip('\n')
            except IOError:
                pdate = None

            adate, articles = parse_articles(res.text)

            if adate != pdate:
                log.info(f'Article date {adate} is different from the previous date {pdate}')
            else:
                log.info(f'Article date {adate} is the same as the previous date, skipping loop')
                continue
            
            with open('prev_sent.time', 'w') as f:
                f.write(adate)

            for article in articles:
                send_tweet(api, generate_tweet(article))
                time.sleep(TWEET_DELAY)

        time.sleep(REFRESH_DELAY)