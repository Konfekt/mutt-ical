This single-file Python script `mutt-ical.py` displays and replies to [Icalendar](https://tools.ietf.org/html/rfc5545) invitations (.ics files) from mutt.
It requires Mutt, Bash and Python with the [Vobject](https://github.com/py-vobject/vobject) Python package which can be installed with `pip install --user vobject`.

Installing
----------

Copy the script into a folder in your `$PATH`, (or specify the `$PATH` in your `mailcap` and `muttrc` files).
Mark it executable by `chmod +x`.
We will assume that you copied it into `~/bin` so that its full path is `~/bin/mutt-ical.py`.

Initial Setup
-------------

* To view the calendar entry in mutt by opening the calendar entry in the attachment view (usually opened by hitting `v` after having selected a mail in mutt), add to your `mailcap` file (found at '`~/.mailcap`, `/etc/mailcap` or `$mailcap_path` set in `muttrc`) the following lines:

```muttrc
text/calendar;    ~/bin/mutt-ical.py -D %s; copiousoutput
text/x-vcalendar; ~/bin/mutt-ical.py -D %s; copiousoutput
application/ics;  ~/bin/mutt-ical.py -D %s; copiousoutput
```

- To view the calendar entry by opening a selected a mail in mutt, add to your .muttrc the following lines:

```muttrc
auto_view text/calendar text/x-vcalendar application/ics text/plain text/html
alternative_order text/calendar text/x-vcalendar application/ics text/plain text/html
```

Here the second line ensures that the calendar entry is displayed before the message text.

- To reply to a calendar entry by pressing `r` in the attachment view (usually opened by hitting `v` after having selected a mail in mutt), add to your .muttrc a line such as

```muttrc
macro attach r \
    "<pipe-entry>iconv -c --to-code=UTF-8 > ~/.cache/mutt.ics<enter><shell-escape>~/bin/mutt-ical.py -i -e your.email@address -s 'msmtp --account=work' ~/.cache/mutt.ics<enter>" \
    "reply to appointment request"
```

Here you need to customize the email address `your.email@address` and the send command `msmtp --account=work`.
If `-s` is not set, the Mutt setting `$sendmail` will be used.

- To optionally open the Icalendar in your favorite desktop calendar application, such as `Ical`, run `xdg-open ~/.cache/mutt.ics` (on Linux, respectively `open ~/.cache/mutt.ics` on Mac OS) after the `mutt-ical.py` command, for example

```muttrc
macro attach r \
    "<pipe-entry>iconv -c --to-code=UTF-8 > ~/.cache/mutt.ics<enter><shell-escape>~/bin/mutt-ical.py -i -e your.email@address -s 'msmtp --account=work' ~/.cache/mutt.ics && xdg-open ~/.cache/mutt.ics<enter>" \
    "reply to appointment request"
```


Usage
-----

If you configure auto_view (as above), then the description should be visible in
the pager.
(Otherwise view the attachements (usually by hitting 'v'), select and open the `Icalendar` entry.)
To reply, just open the `Icalendar` file from mutt:

* View the attachements (usually 'v')
* Select the text/calendar entry
* Hit 'r'
* Choose your reply


Documentation
-------------

The script supports the following options: `-i`, `-a`, `-d`, `-t`, `-D`, and `-s`. The `-e` option followed by an email address and the path to an `.ics` file are required.
If the `-D` option is used, the script will display the event details and terminate without sending any replies.
The `-i`, `-a`, `-d`, and `-t` options are mutually exclusive;
the last one specified determines the response type sent.
By default, the script will use Mutt's sendmail setting to send the reply, unless the `-s` option is used to override it.

```sh
-e <your.email@address>
    Specify the email address to send the reply from. This should be the email address that received the invitation.

-i
    Interactive mode. Prompt for user input to accept, decline, or tentatively accept the invitation.

-a
    Accept the invitation automatically without prompting.

-d
    Decline the invitation automatically without prompting.

-t
    Tentatively accept the invitation automatically without prompting.

-D
    Display only. Show the event details but do not send any reply.

-s <sendmail command>
    Specify the sendmail command to use for sending the email. If not set, the default Mutt setting will be used.

filename.ics
    The .ics file to be processed. This should be the invitation file received.

Usage:

    mutt-ical.py [OPTIONS] -e your@email.address filename.ics
```

Make sure to replace the placeholder `your.email@address` with your actual email address and  `filename.ics` with the path to the .ics file when running the script.

Hints
-----

Mac OS X iCal Users can force iCal to stop trying to send mail on your behalf by replacing
the file `/Applications/iCal.app/Contents/Resources/Scripts/Mail.scpt` with your
own ActionScript. Martin Sander went with the following: `error number -128`
Which tells it that the user cancelled the action.

* Open AppleScript Editor, paste the code from above into a new script, then save it.
* Move the old script `/Applications/iCal.app/Contents/Resources/Scripts/Mail.scpt`  just in case you want to re-enable the functionality.
* Copy your new script into place.

Inspiration
------------

This forks [Martin Sander's](https://github.com/marvinthepa/mutt-ical/) whose (MIT) license restrictions apply, and which was inspired by
[accept.py](http://weirdzone.ru/~veider/accept.py) and [Rubyforge.org Samples](http://vpim.rubyforge.org/files/samples/README_mutt.html).

