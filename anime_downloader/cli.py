import click
import sys
import os

import logging

from anime_downloader.sites import get_anime_class
from anime_downloader.sites.exceptions import NotFoundError
from anime_downloader.players.mpv import mpv
from anime_downloader.__version__ import __version__

from anime_downloader import util
from anime_downloader.config import Config
from anime_downloader import watch as _watch

echo = click.echo


@click.group(context_settings=Config.CONTEXT_SETTINGS)
@click.version_option(version=__version__)
def cli():
    """Anime Downloader

    Download or watch your favourite anime
    """
    pass


# NOTE: Don't put defaults here. Add them to the dict in config
@cli.command()
@click.argument('anime_url')
@click.option(
    '--episodes', '-e', 'episode_range', metavar='<int>:<int>',
    help="Range of anime you want to download in the form <start>:<end>")
@click.option(
    '--url', '-u', type=bool, is_flag=True,
    help="If flag is set, prints the stream url instead of downloading")
@click.option(
    '--play', 'player', metavar='PLAYER',
    help="Streams in the specified player")
@click.option(
    '--skip-download', is_flag=True,
    help="Retrieve without downloading")
@click.option(
    '--download-dir', metavar='PATH',
    help="Specifiy the directory to download to")
@click.option(
    '--quality', '-q', type=click.Choice(['360p', '480p', '720p', '1080p']),
    help='Specify the quality of episode. Default-720p')
@click.option(
    '--force-download', '-f', is_flag=True,
    help='Force downloads even if file exists')
@click.option(
    '--log-level', '-ll', 'log_level',
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
    help='Sets the level of logger')
@click.option(
    '--file-format', '-ff', default='{anime_title}/{anime_title}_{ep_no}',
    help='Format for how the files to be downloaded be named.'
)
@click.pass_context
def dl(ctx, anime_url, episode_range, url, player, skip_download, quality,
        force_download, log_level, download_dir, file_format):
    """ Download the anime using the url or search for it.
    """

    util.setup_logger(log_level)
    util.print_info(__version__)

    cls = get_anime_class(anime_url)

    if not cls:
        anime_url = util.search_and_get_url(anime_url)
        cls = get_anime_class(anime_url)

    try:
        anime = cls(anime_url, quality=quality)
    except Exception as e:
        echo(click.style(str(e), fg='red'))
        return
    if episode_range is None:
        episode_range = '1:'+str(len(anime)+1)

    logging.info('Found anime: {}'.format(anime.title))

    anime = util.split_anime(anime, episode_range)

    if url or player:
        skip_download = True

    if download_dir and not skip_download:
        logging.info('Downloading to {}'.format(os.path.abspath(download_dir)))

    for episode in anime:
        if url:
            util.print_episodeurl(episode)

        if player:
            util.play_episode(episode, player=player)

        if not skip_download:
            episode.download(force=force_download,
                             path=download_dir,
                             format=file_format)
            print()


@cli.command()
@click.argument('anime_name', required=False)
@click.option(
    '--new', '-n', type=bool, is_flag=True,
    help="Create a new anime to watch")
@click.option(
    '--list', '-l', '_list', type=bool, is_flag=True,
    help="List all animes in watch list")
@click.option(
    '--remove', '-r', 'remove', type=bool, is_flag=True,
    help="Remove the specified anime")
@click.option(
    '--quality', '-q', type=click.Choice(['360p', '480p', '720p', '1080p']),
    help='Specify the quality of episode.')
@click.option(
    '--download-dir', metavar='PATH',
    help="Specifiy the directory to download to")
@click.option(
    '--log-level', '-ll', 'log_level',
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
    help='Sets the level of logger', default='INFO')
def watch(anime_name, new, _list, quality, log_level, remove, download_dir):
    """
    With watch you can keep track of any anime you watch.

    Available Commands after selection of an anime:\n
    set      : set episodes_done and title. Ex: set episodes_done=3\n
    remove   : remove selected anime from watch list\n
    update   : Update the episodes of the currrent anime\n
    watch    : Watch selected anime\n
    download : Download episodes of selected anime
    """
    util.setup_logger(log_level)
    util.print_info(__version__)

    watcher = _watch.Watcher()

    if new:
        if anime_name:
            query = anime_name
        else:
            query = click.prompt('Enter a anime name or url', type=str)

        url = util.search_and_get_url(query)

        watcher.new(url)
        sys.exit(0)

    if remove:
        anime = watcher.get(anime_name)
        if anime and click.confirm(
            "Remove '{}'".format(anime.title), abort=True
        ):
            watcher.remove(anime)
        else:
            logging.error("Couldn't find '{}'. "
                          "Use a better search term.".format(anime_name))
            sys.exit(1)
        sys.exit(0)

    if _list:
        list_animes(watcher, quality, download_dir)
        sys.exit(0)

    if anime_name:
        anime = watcher.get(anime_name)
        if not anime:
            logging.error(
                "Couldn't find '{}'."
                "Use a better search term.".format(anime_name))
            sys.exit(1)

        anime.quality = quality

        logging.info('Found {}'.format(anime.title))
        watch_anime(watcher, anime)


def list_animes(watcher, quality, download_dir):
    watcher.list()
    inp = click.prompt('Select an anime', default=1)
    try:
        anime = watcher.get(int(inp)-1)
    except IndexError:
        sys.exit(0)

    # Make the selected anime first result
    watcher.update(anime)

    while True:
        click.clear()
        click.secho('Title: ' + click.style(anime.title,
                                            fg='green', bold=True))
        click.echo('episodes_done: {}'.format(click.style(
            str(anime.episodes_done), bold=True, fg='yellow')))
        click.echo('Length: {}'.format(len(anime)))

        meta = ''
        for k, v in anime.meta.items():
            meta += '{}: {}\n'.format(k, click.style(v, bold=True))
        click.echo(meta)

        click.echo('Available Commands: set, remove, update, watch, download\n')

        inp = click.prompt('Press q to exit', default='q').strip()

        # TODO: A better way to handle commands. Use regex. Refractor to class?
        # Decorator?
        if inp == 'q':
            break
        elif inp == 'remove':
            watcher.remove(anime)
            break
        elif inp == 'update':
            watcher.update_anime(anime)
        elif inp == 'watch':
            anime.quality = quality
            watch_anime(watcher, anime)
            sys.exit(0)
        elif inp.startswith('download'):
            try:
                inp = inp.split('download ')[1]
            except IndexError:
                inp = ':'
            inp = str(anime.episodes_done+1)+inp if inp.startswith(':') else inp
            inp = inp+str(len(anime)) if inp.endswith(':') else inp

            anime = util.split_anime(anime, inp)

            if not download_dir:
                download_dir = Config['dl']['download_dir']

            for episode in anime:
                episode.download(force=False,
                                 path=Config['dl']['download_dir'],
                                 format=Config['dl']['file_format'])
        elif inp.startswith('set '):
            inp = inp.split('set ')[-1]
            key, val = [v.strip() for v in inp.split('=')]
            key = key.lower()

            if key == 'title':
                watcher.remove(anime)
                setattr(anime, key, val)
                watcher.add(anime)
            elif key == 'episodes_done':
                setattr(anime, key, int(val))
                watcher.update(anime)


def watch_anime(watcher, anime):
    to_watch = anime[anime.episodes_done:]
    logging.debug('Sliced epiosdes: {}'.format(to_watch._episodeIds))

    for idx, episode in enumerate(to_watch):

        for tries in range(5):
            logging.info(
                'Playing episode {}'.format(episode.ep_no)
            )
            player = mpv(episode.stream_url)
            returncode = player.play()

            if returncode == mpv.STOP:
                sys.exit(0)
            elif returncode == mpv.CONNECT_ERR:
                logging.warning("Couldn't connect. Retrying.")
                continue
            anime.episodes_done += 1
            watcher.update(anime)
            break
