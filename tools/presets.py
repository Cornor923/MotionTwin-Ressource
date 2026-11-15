"""Réglages de son LabChirp (.lch) : fichiers de paramètres du générateur qui a servi aux bruitages, pas des sons.

Chaque réglage est associé au son du même nom dans le même dossier ; ses paramètres ne sont pas décodés.
"""
import os


def item(game, full, path, ctx):
    return dict(i=path, t='lch', n=os.path.splitext(os.path.basename(path))[0], s=ctx.rel(full), p=path, fmt='LCH',
                c=ctx.collection(game.cfg, path) + ' · réglages LabChirp', z=os.path.getsize(full),
                u=game.source_url(path), x=dict(header=open(full, 'rb').read(11).decode('latin-1')))


def pair(game):
    sounds = {os.path.splitext(it['p'])[0]: it for it in game.items if it['t'] == 'snd' and '#' not in it['p']}
    for it in game.items:
        snd = sounds.get(os.path.splitext(it['p'])[0]) if it['t'] == 'lch' else None
        if snd:
            it['x'].update(snd=snd['s'], snd_name=os.path.basename(snd['p']), snd_id=snd['i'])
