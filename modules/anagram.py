 # -*- coding: utf8 -*-
import re
import requests
import urllib


def anagram(phenny, input):
    """
    Respond with a clever anagram of the given text.

    Inspired by Sternest Meanings, powered by Anagram Genius.
    """
    to_anagram = input.group(2)
    to_anagram = urllib.quote(to_anagram.encode('utf8'), '')
    query = 'http://www.anagramgenius.com/server.php?source_text={}'.format(to_anagram)
    result = requests.get(query)
    # Hooray pre-RESTful internet
    anagram = re.search(
        r"<br><span class=\"black-18\">'(.*)'</span></h3>",
        result.text,
    )
    if anagram:
        phenny.say(anagram.group(1))
    else:
        phenny.say("¯\_(ツ)_/¯")
anagram.rule = (["anagram"], r"(.+)")
