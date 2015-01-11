# coding=utf-8
# AniMess Scanner

from urllib2 import urlopen
import unittest
import re
import os

import VideoFiles
import Stack
import Media



# see tests for matches
RE_EPISODE = re.compile(r'^[\[\(](?P<group>.+?)[\]\)][ _]*'      # [Group] or (Group)
                        r'(?P<show>.+?)[ _]'                     # Title of the show follows
                        r'(S(?P<season>\d+)[ _]+)?'              # S01, S2, etc
                        r'-[ _]'
                        r'(?P<ep>\d+x?)'                         # 01
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
    print 'Animess scan'

    VideoFiles.Scan(path, files, media_list, subdirs)

    # crawl
    for file_path in files:
        episodes = match_episodes(file_path)
        if episodes is not None:
            media_list.extend(episodes)

    # slap it in
    Stack.Scan(path, files, media_list, subdirs)


def match_episodes(file_path):
    match = None
    filename = os.path.basename(file_path)

    # do some cleaning up...
    # filename = re.sub('\([Rr]emastered\)', '', filename)

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

        return episodes


class EpisodeTestCase(unittest.TestCase):
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
                print 'Failed on', filename
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
            '[One-Raws] Check this special - 40.mkv',
            '[Capitalist] Niña y Tanque - 12v2 [DEABBEEF].mkv',
            '[Land-Captalist] Smoke Erryday - 02 (720p) [DEABBEEF].mkv'
        ]
        eps = []
        for filename in episode_filenames:
            new_eps = match_episodes(filename)
            try:
                self.assertGreater(len(new_eps), 0)
            except TypeError:
                print 'Failed:', filename
                raise

            eps += new_eps

        for ep in eps:
            print ep
            if ep.name:
                print '\tTitle:', ep.name

    def test_actually_a_movie(self):
        movie_filenames = [
            "[Capitalist] Normal Guy Monotone B's - The Movie 2nd [BD 1080p AAC] [DEABBEEF].mkv",
            'Tetsuo_(1989)_[1080p,BluRay,x264,DTS]_-_THORA.mkv'
        ]
        for filename in movie_filenames:
            episodes = match_episodes(filename)
            self.assertIsNone(episodes)
