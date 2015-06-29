# coding=utf-8
# AniMess Scanner

from urllib2 import urlopen

import logging
import os
import platform
import re
import unittest

try:
    import VideoFiles
    import Stack
    import Media
except ImportError:
    # copied from the appropriate directories for testing
    from test import VideoFiles, Stack, Media


# see tests for matches
RE_EPISODE = re.compile(r'^[\[\(](?P<group>.+?)[\]\)][ _]*'      # [Group] or (Group)
                        r'(?P<show>.+?)[ _]'                     # Title of the show follows
                        r'(S(?P<season>\d+)[ _]+)?'              # S01, S2, etc
                        r'(-[ _])?'
                        r'(?P<ep>\d+)(?=[ _\.xv])'  # 01
                        r'(-(?P<secondEp>\d+x?))?'               # 01-(02)
                        r'(?P<revision>v\d+)?[ _]*'              # possible end of filename
                        r'((?P<title>[^\(\[].+)[ _]+)?'          # title does not start with a parenthesis
                        r'([\[\(](?P<quality>.+?)[\]\)][ _]*)?'
                        r'([\[\(](?P<quality2>.+?)[\]\)][ _]*)?'
                        r'([\[\(](?P<checksum>.+)[\]\)])?')

# they use their own thing
RE_EPISODE_THORA = re.compile(r'^(?P<show>.+?)_?'
                              r'(S(?P<season>\d+)_)?'
                              r'Ep_?(?P<ep>\d+x?)(-?(?P<secondEp>\d+)x?)?_'
                              r'((?P<revision>v\d+)_)?'
                              r'((?P<title>.+)_)?'
                              r'\[(?P<quality>.+?)\]_'
                              r'-_'
                              r'((?P<collab>.+)-)?THORA'
                              r'( v(?P<revision2>\d+))?')


def Scan(path, files, media_list, subdirs):
    logging.info('Starting Animess scan')

    VideoFiles.Scan(path, files, media_list, subdirs)

    # crawl
    for file_path in files:
        episodes = match_episodes(file_path)
        if episodes is not None:
            media_list.extend(episodes)

            if len(episodes) == 1:
                logging.info('Episode found for {}: {}', file_path, episodes[0])
            else:
                logging.info('Episodes found for {}:'.format(file_path))
                for ep in episodes:
                    logging.info('\t{}'.format(ep))

    # slap it in
    Stack.Scan(path, files, media_list, subdirs)


# for specially named sequels and the like - this is where we give up and directly match heuristics to overcome the
# problem of complex regex. There are also no unit tests for this since I'm planning on replacing this horrible hack
def amend_exceptions(episodes):
    for ep in episodes:
        if ep.show == 'Code Geass R2':
            ep.show = 'Code Geass'
            ep.season = 2

        elif ep.show == 'Tantei Kageki Milky Holmes TD':
            ep.show = 'Tantei Kageki Milky Holmes'
            ep.season = 4

        elif ep.show == 'Mahou Shoujo Lyrical Nanoha StrikerS':
            ep.show = 'Mahou Shoujo Lyrical Nanoha'
            ep.season = 3

        # specials
        elif ep.show == 'Spice and Wolf' and ep.season == 1:
            if ep.episode == 13:
                # if we have episode 13, then we need to kick episodes back
                for sw in filter(lambda e: e.show == 'Spice and Wolf' and e.season == 1 and e.episode > 6, episodes):
                    if sw.episode == 7:
                        sw.season = 0
                        sw.episode = 1
                    else:
                        sw.episode -= 1

        elif ep.show == 'Strike Witches ~Operation Victory Arrow~':
            ep.show = 'Strike Witches'
            ep.season = 0
            ep.episode += 2


def match_episodes(file_path):
    match = None
    filename = os.path.basename(file_path)

    for pattern in [RE_EPISODE_THORA, RE_EPISODE]:
        match = re.match(pattern, filename)
        if match:
            break

    if match:
        show = match.group('show').replace('_', ' ').strip()
        season = match.group('season') if match.group('season') else 1

        ep = match.group('ep')
        if ep.endswith('x'):
            season = 0
            episode_num = int(ep.strip('x'))
        else:
            episode_num = int(match.group('ep'))

        end_episode = int(match.group('secondEp')) if match.group('secondEp') else episode_num
        title = match.group('title').replace('_', ' ').strip() if match.group('title') else None

        episodes = []
        for ep in range(episode_num, end_episode + 1):
            episode = Media.Episode(show, season, episode_num, title=title)
            episode.display_offset = (ep - episode_num) * 100 / (end_episode - episode_num + 1)
            episode.parts.append(file_path)
            episodes.append(episode)

        amend_exceptions(episodes)

        return episodes


# logging and other utilities
# from https://support.plex.tv/hc/en-us/articles/200250417-Plex-Media-Server-Log-Files
_log_map = {
    'linux': [
        '$PLEX_HOME/Library/Application Support/Plex Media Server/Logs/',  # should work 99% of the time
        '/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Logs',  # supported Linux distributions
        '/share/MD0_DATA/.qpkg/PlexMediaServer/Library/Plex Media Server/Logs/',  # QNAP
        '/c/.plex/Library/Application Support/Plex Media Server/Logs/'  # ReadyNAS
        '/Volume1/Plex/Library/Application Support/Plex Media Server/Logs/'  # Synology, Asustor
        '/mnt/HD/HD_a2/plex_conf/Plex Media Server/Logs'  # WD MyCloud
    ],
    'freebsd': [
        '/usr/local/plexdata/Plex Media Server/Logs'  # FreeBSD
        '${JAIL_ROOT}/var/db/plexdata/Plex Media Server/Logs/'  # FreeNAS
    ],
    'darwin': ['$HOME/Library/Application Support/Plex Media Server/Logs'],
    'win32': [
        '%LOCALAPPDATA%\\Plex Media Server\\Logs',
        '%USERPROFILE%\\Local Settings\\Application Data\\Plex Media Server\\Logs'
    ]
}


def _setup_logging():
    try:
        directories = _log_map[platform.system()]
        for path in directories:
            if os.path.exists(path):
                logging.basicConfig(filename=os.path.join(path, 'animess.log'), level=logging.INFO)

    # ignore file logging on unsupported/untested operating systems - mostly pertains to NAS's
    except KeyError:
        logging.basicConfig()


class EpisodeTestCase(unittest.TestCase):
    def setUp(self):
        logging.basicConfig()

    # noinspection PyPep8Naming
    def _get_THORA_packlist(self):
        page = urlopen('http://thoranime.nyaatorrents.org/xdcclist/global/search.php?nick=THORA|Arutha').read()
        page = page.decode('utf8').strip()

        packlist = []
        for line in page.split('\n'):
            # skpip MD5
            if 'rar' in line:
                continue
            title = re.search(r'f:"(.+)"};', line).group(1)
            packlist.append(title)

        return packlist

    # noinspection PyPep8Naming
    def test_THORA(self):
        """
        Tests common THOR Anime episode filename formats
        """
        releases = self._get_THORA_packlist()
        for filename in releases:
            # filter to only episodes
            if not re.search(r'Ep\d+', filename):
                continue

            match = re.match(RE_EPISODE_THORA, filename)
            try:
                self.assertIsNotNone(match)
            except:
                logging.error('Failed on {}'.format(filename))
                raise

            # weak test - we should be able to at least get the show and episode number
            self.assertIsNotNone(match.group('show'))
            self.assertIsNotNone(match.group('ep'))
            if match.group('ep').endswith('x'):
                int(match.group('ep').rstrip('x'))

    def test_episodes(self):
        episode_filenames = [
            '[HorriblyOkaySubs] This Has Spaces S3 - 01 [1080p].mkv',
            '[hh]_Something_wit_underscores_-_02_[DEADBEEF].mkv',
            '[hh]_Something_wit_underscores_-_02_And_a_title!_[DEADBEEF].mkv',
            '[umai] Put a quote\' and extra spaces here2 - 11  (Transcode 720p H264).mkv',
            '[One-Raws] Check this lazy title - 40.mkv',
            '[Capitalist] Niña y Tanque - 12v2 [DEABBEEF].mkv',
            '[Land-Captalist] Smoke Erryday - 02 (720p) [DEABBEEF].mkv',
            '[Coolguise]_Super_High_Quality_Show_09_(1920x1080_Blu-Ray_FLAC)_[DEADBEEF].mkv',
            # sequels
            '[Dreamy] Tantei Kageki Milky Holmes TD - 04 (1280x720 x264 AAC).mkv',
            '[Coldlight]_Mahou_Shoujo_Lyrical_Nanoha_StrikerS_01v3a_DVD[H264][DEADBEEF].mkv',
            'Code_Geass_R2_Ep03_Imprisoned_in_Campus_[720p,BluRay,x264]_-_THORA.mkv',
            '[ReinForce] Strike Witches ~Operation Victory Arrow~ 02 (BDRip 1920x1080 x264 FLAC).mkv'
        ]

        expected_attrs = [
            ('This Has Spaces', 3, 1, None),
            ('Something wit underscores', 1, 2, None),
            ('Something wit underscores', 1, 2, 'And a title!'),
            ('Put a quote\' and extra spaces here2', 1, 11, None),
            ('Check this lazy title', 1, 40, None),
            ('Niña y Tanque', 1, 12, None),
            ('Smoke Erryday', 1, 2, None),
            ('Super High Quality Show', 1, 9, None),
            ('Tantei Kageki Milky Holmes', 4, 4, None),
            ('Mahou Shoujo Lyrical Nanoha', 3, 1, None),
            ('Code Geass', 2, 3, 'Imprisoned in Campus'),
            ('Strike Witches', 0, 4, None)
        ]

        eps = []
        for filename in episode_filenames:
            new_eps = match_episodes(filename)
            try:
                self.assertGreater(len(new_eps), 0)
            except TypeError:
                logging.error('Failed: {}'.format(filename))
                raise

            eps += new_eps

        for ep, expected in zip(eps, expected_attrs):
            self.assertEqual(ep.show, expected[0])
            self.assertEqual(str(ep.season), str(expected[1]))
            self.assertEqual(str(ep.episode), str(expected[2]))
            self.assertEqual(ep.name, expected[3])

    def test_actually_a_movie(self):
        movie_filenames = [
            "[Capitalist] Normal Guy Monotone B's - The Movie 2nd [BD 1080p AAC] [DEABBEEF].mkv",
            'Tetsuo_(1989)_[1080p,BluRay,x264,DTS]_-_THORA.mkv'
        ]
        for filename in movie_filenames:
            episodes = match_episodes(filename)
            self.assertIsNone(episodes)

_setup_logging()