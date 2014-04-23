#!/usr/bin/env python
"""
karma.py - Phenny karma Module
"""

import time
import random
import pickle
import string
from modules import filename

SHOW_TOP_DEFAULT = 6
KVERSION = "0.1.6"

REMOVE_LINK = -1
OFFER_MERGE = 0
OFFER_VERIFIED = 1
SET_PRIMARY = 2
CHECK_LINK_CHANGED = 3
CHECK_LINK_CHANGER = 4

class KarmaNode(object):
    def __init__(self):
        # organizational
        self._parent = None  # the parent/children distinction is arbitrary
        self._children = set()
        # linked values, may hold junk if not root
        self._reset_linked()
        # raw values
        self._karma = 0
        self._contrib_plus = 0
        self._contrib_minus = 0

    def _set_and_link(attr):
        def anon(self, value):
            diff = value - getattr(self.root(), "_linked" + attr)
            setattr(self.root(), "_linked" + attr, value)
            setattr(self, attr, getattr(self, attr) + diff)
        return anon

    karma = property(
        lambda self: self.root()._linked_karma,
        _set_and_link("_karma"))
    contrib_plus = property(
        lambda self: self.root()._linked_contrib_plus,
        _set_and_link("_contrib_plus"))
    contrib_minus = property(
        lambda self: self.root()._linked_contrib_minus,
        _set_and_link("_contrib_minus"))

    def recalculate_karma(self):
        """Assumes self is root"""
        self._linked_karma = 0
        self._linked_contrib_plus = 0
        self._linked_contrib_minus = 0
        # BFS with acyclical guarantee
        q = set([self])
        while q:
            t = q.pop()
            self._add_to_linked(t)
            q |= t._children

    def root(self):
        while self._parent is not None:
            self = self._parent
        return self

    def make_root(self, new_parent=None):
        if new_parent is None:
            self._set_linked(self.root())
        else:
            new_parent.root()._add_linked(self.root())
        while self is not None:
            self._children.discard(new_parent)
            if new_parent is not None:
                new_parent._children.add(self)
            # my parent becomes new_parent, my old parent becomes self, and I am the new parent
            self._parent, self, new_parent = new_parent, self._parent, self


    def _set_parent(self, parent):
        """Only sets the link, does no checks or updates"""
        self._parent = parent
        parent._children.add(self)

    def is_alias(self, other):
        """Returns true if self and other are in the same alias group, else false"""
        return self.root() == other.root()

    def add_alias(self, other):
        rself, rother = self.root(), other.root()
        if rself is rother:  # graph must be acyclical
            return False
        if self._parent is None:
            self._set_parent(other)
            rother._add_linked(self)
        elif other._parent is None:
            other._set_parent(self)
            rself._add_linked(other)
        else:  # decide on one to be the parent
            other.make_root(self)
        return True

    def remove_alias(self, other):
        if self._parent is other:
            other, self = self, other
        if other._parent is self:
            other._parent = None
            self._children.remove(other)
            other.recalculate_karma()
            self.root()._sub_linked(other)
            return True
        return False

    def __str__(self):
        return "".join((hex(id(self)), "(", hex(id(self._parent)), " [",
            ", ".join(map(lambda q: hex(id(q)), self._children)), "])"))


def _generic_linked(value_fn):
    def anon(self, other=None):
        for name in (
                "_karma",
                "_contrib_plus",
                "_contrib_minus"):
            setattr(self, "_linked" + name, value_fn(self, other, name))
    return anon

setattr(KarmaNode, "_reset_linked", _generic_linked(lambda _, __, ___: 0))
setattr(KarmaNode, "_set_linked", _generic_linked(
    lambda self, other, name: getattr(other, "_linked" + name)))
setattr(KarmaNode, "_sub_linked", _generic_linked(
    lambda self, other, name: getattr(self, "_linked" + name) - getattr(other, "_linked" + name)))
setattr(KarmaNode, "_sub_from_linked", _generic_linked(
    lambda self, other, name: getattr(self, "_linked" + name) - getattr(other, name)))
setattr(KarmaNode, "_add_linked", _generic_linked(
    lambda self, other, name: getattr(self, "_linked" + name) + getattr(other, "_linked" + name)))
setattr(KarmaNode, "_add_to_linked", _generic_linked(
    lambda self, other, name: getattr(self, "_linked" + name) + getattr(other, name)))


def setup(self):
    self.alias_tentative = {}
    self.fooled = False
    try:
        f = open(filename(self, "karma"), "r")
        self.karmas = pickle.load(f)  # TODO: after the upgrade change to:
        # version, self.karmas = pickle.load
        f.close()
        # TODO: and then get rid of this upgrade code
        try:
            self.karmas[0]
        except KeyError:  # old version
            temp = {}
            for key, karma in self.karmas.items():
                temp[key] = KarmaNode()
                temp[key].karma = karma
            self.karmas = temp
            try:
                f = open(filename(self, "karma_contrib"), "r")
                kcont = pickle.load(f)
                f.close()
                for k, (plus, minus) in kcont.items():
                    kn = self.karmas.setdefault(k, KarmaNode())
                    kn.contrib_plus = plus
                    kn.contrib_minus = minus
            except IOError:
                pass
            save_karma(self)
        else:
            version, self.karmas = self.karmas  # TODO: yell (or upgrade) on version mismatch
    except IOError:
        pass
    klist = list(self.karmas)
    self.fools_dict = dict(zip(klist, klist[1:] + [klist[0]]))

def save_karma(self):
    if self.fooled and not is_fools():
        for nick, node in self.karmas.items():
            del node.fools_talk
        self.fooled = False
    try:
        f = open(filename(self, "karma"), "w")
        pickle.dump((KVERSION, self.karmas), f)
        f.close()
    except IOError:
        pass

def karma_me(phenny, input):
    target = input.group(1).lower()
    karma = (input.group(2) == "++") * 2 - 1
    sender = input.nick.lower()
    if not hasattr(phenny, 'karmas'):
        return phenny.say('error?')

    target_nicks = set([target])
    sender_nicks = set([sender])
    if target in phenny.alias_list:
        target_nicks.add(phenny.alias_list[target])
    if sender in phenny.alias_list:
        sender_nicks.add(phenny.alias_list[sender])
    now = time.time()
    for s in sender_nicks:
        s = phenny.karmas.get(s, KarmaNode())
        for t in target_nicks:  # target and sender must be disjoint
            if phenny.karmas.get(t, KarmaNode()).is_alias(s):
                if hasattr(s, "last_beak") and s.last_beak + 60 > now:
                    return phenny.say("lol sick beak")
                if is_fools():
                    return report_karma_update(phenny, input.nick)
                return phenny.say("I'm sorry, "+input.nick+". I'm afraid I can't do that.")

    for t in target_nicks:
        if t in phenny.seen:  # i at least know who you're talking about.
            # send_out = []
            # if target not in phenny.karmas:
            #     alias_tentative[target] = [CHECK_LINK_CHANGED, input.sender, sender, karma]
            #     send_out.append(target)
            # elif sender not in phenny.karmas:
            #     alias_tentative[sender] = [CHECK_LINK_CHANGER, input.sender, target, karma]
            #     send_out.append(sender)
            # else:
            #     change_karma(phenny, target, sender, karma)

            # for o in send_out:
            #     phenny.msg("nickserv", "info " + o)
            change_karma(phenny, target, sender, karma)
            return True
    phenny.notice(input.nick, "I'm sorry. I'm afraid I do not know who that is.")
karma_me.rule = r'(\S+?)[ :,]{0,2}(\+\+|--)\s*$'

def change_karma(phenny, target, sender, karma):
    phenny.karmas.setdefault(target, KarmaNode()).karma += karma
    phenny.karmas.setdefault(sender, KarmaNode())
    if karma == -1:
        phenny.karmas[sender].contrib_minus += 1
    else:
        phenny.karmas[sender].contrib_plus += 1
    report_karma_update(phenny, target)
    save_karma(phenny)

# def verify_nickserv_alias(phenny, input):
#     if input.nick.lower() != "nickserv":
#         return
#     off_acct = input.group(1).lower()
#     main_acct = input.group(2).lower()
#     if off_acct.lower() not in phenny.alias_tentative:
#         return

#     data = phenny.alias_tentative[off_acct]
#     if data[0] in (CHECK_LINK_CHANGED, CHECK_LINK_CHANGER):
#         action, return_addr, target, amt = data
#         del phenny.alias_tentative[off_acct]
#         if off_acct not in phenny.karmas:
#             off_karma = KarmaNode()
#             phenny.karmas[off_acct] = off_karma
#             if off_acct != main_acct:
#                 main_karma = phenny.karmas.setdefault(main_acct, KarmaNode())
#                 main_karma.add_alias(off_karma)
#         if target not in phenny.alias_tentative:  # done
#             if action == CHECK_LINK_CHANGED:
#                 change_karma(phenny, off_acct, target, amt)
#             else:
#                 change_karma(phenny, target, off_acct, amt)
# verify_nickserv_alias.event = "NOTICE"
# verify_nickserv_alias.rule = r"Information on (\w+) \(account (\w+)\):"
# verify_nickserv_alias.priority = "low"
# verify_nickserv_alias.thread = False

def get_karma(phenny, input):
    """Fetch the karma of the given user. If no user is given, or with optional parameters 'top x', gives top and bottom x leaders in karma."""
    if not hasattr(phenny, 'karmas'):
        return phenny.say('error?')
    show_top = input.group(3)
    contrib = input.group(4)
    if show_top is not None:  # want to show the top x
        nick = None
        show_top = int(show_top)
    elif contrib is not None:  # want to show how much karma someone's changed
        lcontrib = contrib.lower()
        if lcontrib not in phenny.karmas or not (
                phenny.karmas[lcontrib].contrib_plus or
                phenny.karmas[lcontrib].contrib_minus):
            phenny.say(contrib + " has not altered any karma.")
            return
        up, down = map(str, (phenny.karmas[lcontrib].contrib_plus, phenny.karmas[lcontrib].contrib_minus))
        if is_fools():
            down, up = up, down
        phenny.say(' '.join((contrib, "has granted", up, "karma and removed", down, "karma.")))
        return
    else:
        nick = input.group(2)
        show_top = SHOW_TOP_DEFAULT
    if nick:
        nick = nick.lower()
        if nick in phenny.karmas:
            phenny.say(nick + " has " + str(report_karma_update(phenny, nick, silent=True)) + " karma.")
        else:
            phenny.say("That entity does not exist within the karmaverse")
    elif len(phenny.karmas) > 0:
        all_karm = dict(((key, kn.karma) for key, kn in phenny.karmas.items()))
        karm = dict(((key, kn.karma) for key, kn in phenny.karmas.items() if kn.root() == kn))  # remove duplicates due to aliases
        s_karm = sorted(karm, key=karm.get, reverse=True)
        if is_fools():
            s_karm = [phenny.fools_dict[u] for u in s_karm]
            all_karm = dict(((key, karma / 2 - 5) for key, karma in all_karm.items()))
        msg = ', '.join([x + ": " + str(all_karm[x]) for x in s_karm[:show_top]])
        if msg:
            phenny.say("Best karma: " + msg)
        worst_karmas = ', '.join([x + ": " + str(all_karm[x])
                for x in s_karm[:-show_top-1:-1] if all_karm[x] < 0])
        if worst_karmas:
            phenny.say("Worst karma: "+ worst_karmas)
    else:
        phenny.say("You guys don't have any karma apparently.")
get_karma.name = 'karma'
get_karma.rule = (["karma"], r'(?:(top +(\d)|contrib +(\S+)|\S+))?\s*$')

def stupid_test(phenny, input):
    """Stupid friggin test."""
    if input.group(2) is None:
        phenny.say("Incredibly stupid.")
    else:
        phenny.say('stupid: ' + input.group(2))
stupid_test.name = 'karma stupid'
stupid_test.rule = (['karma'], r'stupid +(\d)$')

def set_primary_alias(phenny, input):
    """Set your primary alias, to be displayed in the karma rankings"""
    nick = input.nick
    target = input.group(2)
    if target is None:
        target = nick
    phenny.alias_tentative[nick.lower()] = [SET_PRIMARY, input.sender, target.lower()]
    phenny.say("Karma primary initiated.")
    phenny.write(['WHOIS'], nick)  # logic continued in karma_id
set_primary_alias.name = "kprimary"
set_primary_alias.rule = (["kprimary"], r'(\S+)?\s?$')

def nuke_karma(phenny, input):
    if input.nick not in phenny.ident_admin: return phenny.notice(input.nick, 'Requires authorization. Use .auth to identify')
    nick = input.group(2)
    if nick:
        nick = nick.lower()
        if nick in phenny.karmas:
            del phenny.karmas[nick]
            phenny.say(input.group(2) + " has been banished from the karmaverse")
            save_karma(phenny)
nuke_karma.name = 'knuke'
nuke_karma.rule = (["knuke"], r'(\S+)$')

def beaked_on(phenny, input):
    """Lol sick beak"""
    nick = input.nick.lower()
    if nick in phenny.karmas:
        phenny.karmas[nick].last_beak = time.time()
beaked_on.rule = r"(?i)sick\s+beak"

def karma_alias(phenny, input):
    """Share your karma with another nick you use."""
    nick = input.nick
    target = input.group(2)
    phenny.say("sender: %s, target: %s" % (nick, target))
    if target == "-f":
        return False
    if target is None:
        return
    phenny.alias_tentative[nick.lower()] = [OFFER_MERGE, input.sender, target.lower()]
    phenny.say("Karma merge offer initiated.")
    phenny.write(['WHOIS'], nick)  # logic continued in karma_id
karma_alias.name = 'klias'
karma_alias.rule = (["klias", "kmerge"], r"(\S+)\s?$")

def rm_karma_alias(phenny, input):
    """Remove the link between two nicks."""
    nick = input.nick
    target = input.group(2)
    if target == "-f":
        return False
    if target is None:
        return
    phenny.alias_tentative[nick.lower()] = [REMOVE_LINK, input.sender, target.lower()]
    phenny.say("Karma merge split initiated.")
    phenny.write(['WHOIS'], nick)  # logic continued in karma_id
rm_karma_alias.name = "rm_klias"
rm_karma_alias.rule = (["rm_klias", "kdemerge"], r"(\S+)\s?$")

def force_karma_alias(phenny, input):
    if input.nick not in phenny.ident_admin: return phenny.notice(input.nick, 'Requires authorization. Use .auth to identify')
    target1 = input.group(2)
    target2 = input.group(3)
    karma1 = phenny.karmas.setdefault(target1.lower(), KarmaNode())
    karma2 = phenny.karmas.setdefault(target2.lower(), KarmaNode())
    if karma1.add_alias(karma2):
        phenny.say("%s and %s successfully kliased." % (target1, target2))
    elif karma1.is_alias(karma2):
        phenny.say("%s is already %s." % (target1, target2))
    else:
        phenny.say("klias failed.")
force_karma_alias.rule = (["klias", "kmerge"], r"-f\s+(\S+)\s+(\S+)\s?$")

def force_rm_karma_alias(phenny, input):
    if input.nick not in phenny.ident_admin: return phenny.notice(input.nick, 'Requires authorization. Use .auth to identify')
    targets = (input.group(2), input.group(3))
    target1, target2 = map(string.lower, targets)
    if target1 not in phenny.karmas or target2 not in phenny.karmas:
        return phenny.say("rm_klias failed.")
    karma1 = phenny.karmas[target1]
    karma2 = phenny.karmas[target2]
    if karma1.remove_alias(karma2):
        phenny.say("%s and %s successfully unlinked." % targets)
    elif not karma1.is_alias(karma2):
        phenny.say("%s and %s are not linked." % targets)
    else:
        phenny.say("Could not unlink %s and %s." % targets)
force_rm_karma_alias.rule = (["rm_klias", "kdemerge"], r"-f\s+(\S+)\s+(\S+)\s?$")

def karma_id(phenny, input):
    logged_in_as = input.args[2].lower()
    if logged_in_as in phenny.alias_tentative:  # you're looking for someone
        data = phenny.alias_tentative[logged_in_as]
        nick = input.args[1]
        if logged_in_as != nick.lower():  # logged in as someone else
            return phenny.msg(sender, "You must be logged in as " + nick)
        if action == OFFER_MERGE:  # add link
            action, sender, target = data
            data[0] = OFFER_VERIFIED  # verified
            if target in phenny.alias_tentative:  # he was looking for someone too
                tverified, _, tstarget = phenny.alias_tentative[target]
                if tverified == OFFER_VERIFIED and tstarget == logged_in_as:  # done.
                    node1 = phenny.karmas[tstarget]
                    node2 = phenny.karmas[target]
                    if node1.add_alias(node2):
                        phenny.msg(sender, "You got it, " + target)
                    elif node1.is_alias(node2):
                        phenny.msg(sender, "You're already that guy.")
                    else:
                        phenny.msg(sender, "Karma alias failed.")
                    del phenny.alias_tentative[target]
                    del phenny.alias_tentative[tstarget]
        elif action == REMOVE_LINK:  # remove link
            action, sender, target = data
            node1 = phenny.karmas[logged_in_as]
            node2 = phenny.karmas[target]
            if node1.remove_alias(node2):
                phenny.msg(sender, "You are no longer also known as " + target)
            elif not node.is_alias(node2):
                phenny.msg(sender, "You are not that guy already.")
            else:
                phenny.msg(sender, "Karma alias removal failed.")
            del phenny.alias_tentative[logged_in_as]
        elif action == SET_PRIMARY:  # set primary
            action, sender, target = data
            new_primary = phenny.karmas[target]
            node = phenny.karmas[logged_in_as]
            if new_primary.is_alias(node):
                new_primary.make_root()
                phenny.msg(sender, "Your primary nick is now " + logged_in_as)
            else:
                phenny.msg(sender, "You're not even that guy.")
            del phenny.alias_tentative[logged_in_as]
karma_id.event = "330"
karma_id.rule = r"(.*)"
karma_id.priority = "low"

def fools_speech(phenny, input):
    if is_fools():
        phenny.fooled = True
        node = phenny.karmas.setdefault(input.nick.lower(), KarmaNode())
        try:
            node.fools_talk += 1
        except AttributeError:
            node.fools_talk = 1
        if node.fools_talk > random.randint(25, 100):
            node.fools_talk = -float("inf")
            nick = input.nick
            if random.randint(0, 9):
                report_karma_update(phenny, nick)
            else:
                phenny.say("%s has been banished from the karmaverse" % nick)
fools_speech.rule = r"(.*)"

def is_fools():
    return time.strftime("%m %d") == "04 01"  # shut up

def report_karma_update(phenny, nick, silent=False):
    if is_fools():
        lnick = nick.lower()
        if lnick not in phenny.fools_dict:
            phenny.fools_dict["mithorium"], phenny.fools_dict[lnick] = (
                lnick, phenny.fools_dict["mithorium"])
        value = phenny.karmas[phenny.fools_dict[lnick]].karma
    else:
        value = phenny.karmas[nick].karma
    if not silent:
        phenny.say(nick + "'s karma is now " + str(value))
    return value

if __name__ == '__main__':
    print __doc__.strip()
