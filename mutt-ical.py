#!/usr/bin/env python3

"""
This script is meant as a simple way to reply to ical invitations from mutt.
See README for instructions and LICENSE for licensing information.

Note on dependencies and compatibility:
- This script depends on the 'vobject' package for iCalendar parsing/serialization.
- Ensure a recent 'vobject' (e.g., 0.9.7 or newer) is installed for best compatibility with modern Python.
- Some older 'vobject' versions may have issues with recent Python releases. If you encounter parsing/serialization problems,
  consider upgrading 'vobject' or using an alternative like 'icalendar'.
"""

__author__ = "Martin Sander"
__license__ = "MIT"

import locale
import subprocess
import sys
import time
import shlex
import re
from datetime import datetime, timezone
from email.message import EmailMessage
from getopt import gnu_getopt as getopt

import vobject

usage = """
usage:
%s [OPTIONS] -e your@email.address filename.ics
OPTIONS:
    -i interactive
    -a accept
    -d decline
    -t tentatively accept (accept is default, last one wins)
    -D display only
    -s <sendmail command>
""" % sys.argv[0]


def del_if_present(dic, key):
    if key in dic:
        del dic[key]


def set_accept_state(attendees, state):
    # Normalize RSVP-related parameters for each attendee and set participation status
    if not isinstance(attendees, list):
        return attendees
    for attendee in attendees:
        if not hasattr(attendee, "params"):
            continue
        attendee.params['PARTSTAT'] = [state]
        for i in ["RSVP", "ROLE", "X-NUM-GUESTS", "CUTYPE"]:
            del_if_present(attendee.params, i)
    return attendees


def get_accept_decline():
    # Get user input for accept/decline/tentative/cancel in interactive mode
    while True:
        sys.stdout.write("\nAccept Invitation? [Y]es/[n]o/[t]entative/[c]ancel\n")
        ans = sys.stdin.readline()
        if ans.lower() == 'y\n' or ans == '\n':
            return 'ACCEPTED'
        if ans.lower() == 'n\n':
            return 'DECLINED'
        if ans.lower() == 't\n':
            return 'TENTATIVE'
        if ans.lower() == 'c\n':
            print("aborted")
            sys.exit(1)


def get_answer(invitation):
    # Build the REPLY VCALENDAR/VEVENT from the invitation
    ans = vobject.newFromBehavior('vcalendar')
    ans.add('method')
    ans.method.value = "REPLY"
    ans.add('vevent')

    # just copy from invitation
    for i in ["uid", "summary", "dtstart", "dtend", "organizer", "vtimezone"]:
        if i in invitation.vevent.contents:
            ans.vevent.add(invitation.vevent.contents[i][0])

    # new timestamp
    ans.vevent.add('dtstamp')
    ans.vevent.dtstamp.value = datetime.now(timezone.utc)
    return ans


def execute(command, mailtext):
    # Execute an external command optionally feeding it data through stdin
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    if process.stdin is not None and mailtext is not None:
        if isinstance(mailtext, str):
            mailtext = mailtext.encode()
        process.stdin.write(mailtext)
        process.stdin.close()

    result = None
    while result is None:
        result = process.poll()
        time.sleep(.1)
    if result != 0:
        print("unable to send reply, subprocess exited with\
                exit code %d\nPress return to continue" % result)
        sys.stdin.readline()


def openics(invitation_file):
    # Open and parse the ICS invitation file
    with open(invitation_file, encoding=locale.getpreferredencoding(False)) as f:
        return vobject.readOne(f, ignoreUnreadable=True)


def format_date(value: datetime) -> str:
    # Format a datetime-like value for display in local timezone when possible
    if isinstance(value, datetime):
        try:
            return value.astimezone(tz=None).strftime("%Y-%m-%d %H:%M %z")
        except Exception:
            return value.strftime("%Y-%m-%d %H:%M %z")
    return value.strftime("%Y-%m-%d %H:%M %z")


def display(ical):
    # Display event details to the user
    summary = ical.vevent.contents['summary'][0].value
    if 'organizer' in ical.vevent.contents:
        if hasattr(ical.vevent.organizer, 'EMAIL_param'):
            sender = ical.vevent.organizer.EMAIL_param
        else:
            sender = ical.vevent.organizer.value.split(':')[1]  # workaround for MS
    else:
        sender = "NO SENDER"
    if 'description' in ical.vevent.contents:
        description = ical.vevent.contents['description'][0].value
    else:
        description = "NO DESCRIPTION"
    attendees = ical.vevent.contents.get("attendee", [])
    locations = ical.vevent.contents.get("location", None)
    sys.stdout.write("From:\t" + sender + "\n")
    sys.stdout.write("Title:\t" + summary + "\n")
    sys.stdout.write("To:\t")
    for attendee in attendees:
        if hasattr(attendee, 'EMAIL_param') and hasattr(attendee, 'CN_param'):
            sys.stdout.write(attendee.CN_param + " <" + attendee.EMAIL_param + ">, ")
        else:
            try:
                sys.stdout.write(attendee.CN_param + " <" + attendee.value.split(':')[1] + ">, ")  # workaround for MS
            except Exception:
                # workaround for 'mailto:' in email
                sys.stdout.write(attendee.value.split(':')[1] + " <" + attendee.value.split(':')[1] + ">, ")
    sys.stdout.write("\n")
    if hasattr(ical.vevent, 'dtstart'):
        print(f"Start:\t{format_date(ical.vevent.dtstart.value)}")
    if hasattr(ical.vevent, 'dtend'):
        print(f"End:\t{format_date(ical.vevent.dtend.value)}")
    if locations:
        sys.stdout.write("Location:\t")
        for location in locations:
            if location.value:
                sys.stdout.write(location.value + ", ")
        sys.stdout.write("\n")
    sys.stdout.write("\n")
    sys.stdout.write(description + "\n")


def sendmail_command():
    # Detect the configured sendmail command from mutt/neomutt configuration
    for mutt in ("mutt", "neomutt"):
        try:
            output = subprocess.check_output([mutt, "-Q", "sendmail"], stderr=subprocess.STDOUT)
            out = output.strip().decode()
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue

        match = re.search(r'sendmail\s*=\s*"([^"]+)"', out)
        if match:
            return shlex.split(match.group(1))

        match = re.search(r'sendmail\s*=\s*(\S.*)$', out)
        if match:
            return shlex.split(match.group(1))

        if out:
            out = out.strip('"')
            return shlex.split(out)

    return None


def organizer(ical):
    # Extract organizer email address from event
    if 'organizer' in ical.vevent.contents:
        if hasattr(ical.vevent.organizer, 'EMAIL_param'):
            return ical.vevent.organizer.EMAIL_param
        return ical.vevent.organizer.value.split(':')[1]  # workaround for MS
    raise Exception("no organizer in event")


if __name__ == "__main__":
    # Parse options and drive the interactive or non-interactive reply flow
    sendmail_resolver = sendmail_command
    email_address = None
    accept_decline = 'ACCEPTED'
    opts, args = getopt(sys.argv[1:], "s:e:aidtD")

    if len(args) < 1:
        sys.stderr.write(usage)
        sys.exit(1)

    invitation = openics(args[0])
    display(invitation)

    for opt, arg in opts:
        if opt == '-D':
            sys.exit(0)
        if opt == '-s':
            # If -s is provided, override sendmail with a lambda that returns the command
            sendmail_resolver = (lambda a=arg: shlex.split(a))
        if opt == '-e':
            email_address = arg
        if opt == '-i':
            accept_decline = get_accept_decline()
        if opt == '-a':
            accept_decline = 'ACCEPTED'
        if opt == '-d':
            accept_decline = 'DECLINED'
        if opt == '-t':
            accept_decline = 'TENTATIVE'

    if not email_address:
        sys.stderr.write("Error: Your email address must be provided with -e.\n")
        sys.stderr.write(usage)
        sys.exit(1)

    ans = get_answer(invitation)

    attendees = invitation.vevent.contents.get("attendee", [])
    set_accept_state(attendees, accept_decline)

    ans.vevent.add('attendee')
    ans.vevent.attendee_list.pop()
    flag = 1
    for attendee in attendees:
        if hasattr(attendee, 'EMAIL_param'):
            if attendee.EMAIL_param.lower() == email_address.lower():
                ans.vevent.attendee_list.append(attendee)
                flag = 0
        else:
            if attendee.value.split(':')[1].lower() == email_address.lower():
                ans.vevent.attendee_list.append(attendee)
                flag = 0
    if flag:
        sys.stderr.write("Seems like you have not been invited to this event!\n")
        sys.exit(1)

    summary = ans.vevent.contents['summary'][0].value
    accept_decline = accept_decline.capitalize()
    subject = f"{accept_decline}: {summary}"
    to = organizer(ans)

    ans.vevent.add('priority')
    ans.vevent.priority.value = '5'

    message = EmailMessage()
    message['From'] = email_address
    message['To'] = to
    message['Subject'] = subject
    if accept_decline.lower() == "accepted":
        mailtext = f"Thank you for the invitation. I, {email_address}, will be attending."

        ans.vevent.add('status')
        ans.vevent.status.value = 'CONFIRMED'
        ans.vevent.add('x-microsoft-cdo-busystatus')
        ans.vevent.x_microsoft_cdo_busystatus.value = 'BUSY'
    elif accept_decline.lower() == "tentative":
        mailtext = f"Thank you for the invitation. I, {email_address}, am tentatively available and have marked this time on my calendar."

        ans.vevent.add('status')
        ans.vevent.status.value = 'TENTATIVE'
        ans.vevent.add('x-microsoft-cdo-busystatus')
        ans.vevent.x_microsoft_cdo_busystatus.value = 'TENTATIVE'
    elif accept_decline.lower() == "declined":
        mailtext = f"Thank you for the invitation. Unfortunately, I, {email_address}, will not be able to attend."
    else:
        mailtext = "Invalid response type provided."

    message.add_alternative(mailtext, subtype='plain')
    message.add_alternative(
        ans.serialize(),
        subtype='calendar',
        params={'method': 'REPLY', 'component': 'VEVENT', 'name': 'reply.ics'}
    )

    sendmail_cmd = sendmail_resolver() if callable(sendmail_resolver) else sendmail_resolver
    if not sendmail_cmd:
        raise RuntimeError("Sendmail command is not configured. Aborting.")

    subprocess.run(sendmail_cmd, input=message.as_bytes(), check=True)

    # # From https://github.com/marvinthepa/mutt-ical/commit/c62488fbfa6a817e0f03f808c8cc14d771ce3c2d#diff-3248d42797b254937d2a6b11a3980df7c90a128ba41931a0dc8f4c1ed2c51d13R224
    # if accept_decline in {'ACCEPTED', 'TENTATIVE'}:
    #     # add to khal
    #     khal = {}
    #     khal['dtstart'] = None
    #     khal['dtend'] = None
    #     khal['summary'] = invitation.vevent.contents['summary'][0].value
    #     if hasattr(invitation.vevent, 'dtstart'):
    #         khal['dtstart'] = invitation.vevent.dtstart.value.astimezone(tz=None).strftime("%Y-%m-%d %H:%M")
    #     if hasattr(invitation.vevent, 'dtend'):
    #         khal['dtend'] = invitation.vevent.dtend.value.astimezone(tz=None).strftime("%Y-%m-%d %H:%M")
    #     if 'description' in invitation.vevent.contents:
    #         khal['summary'] += " :: "
    #         khal['summary'] += invitation.vevent.contents['description'][0].value
    #     execute(['khal', 'new', khal['dtstart'], khal['dtend'], khal['summary']], None)
