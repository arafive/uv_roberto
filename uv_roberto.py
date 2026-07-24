"""
Creazione: Thu Jul 23 14:54:47 2026
Autore: daniele.carnevale
"""

import os
import sys
import ast
import configparser
import warnings
warnings.filterwarnings('ignore', category=UserWarning)

import locale
locale.setlocale(locale.LC_TIME, 'it_IT.UTF-8')

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import matplotlib.image as mpimg
from matplotlib.collections import LineCollection
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from scipy.interpolate import make_interp_spline
from datetime import datetime, timezone

sys.path.insert(0, os.path.expanduser('~/.config'))
from config_percorsi_Daniele import CARTELLA_REPO_ROOT

cartella_lavoro = os.path.join(CARTELLA_REPO_ROOT, 'uv_roberto')
os.chdir(cartella_lavoro)

from matplotlib import font_manager
font_files = font_manager.findSystemFonts(fontpaths='NotoSansNerdFont')
for font_file in font_files:
    font_manager.fontManager.addfont(font_file)

plt.rc('font', family=font_manager.FontProperties(fname=font_file).get_name(), weight='normal', size=10)

from danilib import f_settaggio_db_arpal
connessione = f_settaggio_db_arpal()

# config = configparser.ConfigParser()
# config.read('./config.ini')

def get_colore(valore, dict_colori):
    for colore, (lo, hi) in dict_colori.items():
        if lo <= valore <= hi:
            return colore
    return 'gray'

def formatta_tick(x, pos):
    data = mdates.num2date(x)
    if data.hour == 0:
        return data.strftime('%a\n%d %b')
    elif data.hour in [3, 9, 15, 21]:
        return ''
    else:
        return data.strftime('%H:00')
    
plot_uvmax, spessore_uvmax = True, 0.3

# %%
# for delay in np.arange(0, 90, 1):
#     for m in [0, 30]:
#         adesso_timestamp = pd.to_datetime(datetime.now(timezone.utc)).tz_localize(None).floor('30min') - pd.Timedelta(hours=delay) - pd.Timedelta(minutes=m)

adesso_timestamp = pd.to_datetime(datetime.now(timezone.utc)).tz_localize(None).floor('30min')

giorno_oggi = adesso_timestamp.normalize()
gg3_ts = giorno_oggi - pd.Timedelta(days=2)
x_max_asse_ts = giorno_oggi + pd.Timedelta(days=1)

adesso = adesso_timestamp.strftime('%Y%m%d%H%M')
gg3 = gg3_ts.strftime('%Y%m%d%H%M')

print(adesso_timestamp)

query = f"""
SELECT
    DATA.CODE,
    DATA.DTRF,
    ANAG.NAME,
    UVINDM / 100 as UV_MEDIA,
    UVINDX / 100 as UV_MASSIMA
FROM
    DATA, ANAG
WHERE
    DATA.CODE = ANAG.CODE AND
    DATA.DTRF > TO_DATE('{gg3}', 'YYYYMMDDHH24MI') AND
    DATA.DTRF <= TO_DATE('{adesso}', 'YYYYMMDDHH24MI')
    AND DATA.CODE IN ('CFUNZ', 'SPZIA')
    AND TO_CHAR(DATA.DTRF, 'MI') IN ('00', '30')
ORDER BY DATA.DTRF
"""

df_query = pd.read_sql(query, con=connessione)

dizionario_df = {
    code: gruppo[['DTRF', 'NAME', 'UV_MEDIA', 'UV_MASSIMA']]
        .assign(DTRF=lambda d: d['DTRF'].dt.tz_localize('UTC').dt.tz_convert('Europe/Rome').dt.tz_localize(None))
        .set_index('DTRF').rename_axis('')
    for code, gruppo in df_query.groupby('CODE')
}
del (df_query)

# %%

# Palette -> https://www.sciencedirect.com/science/article/pii/S2666469023000210

dict_colori = {
    '#97D700': [0, 2.50],
    '#FCE300': [2.50, 5.50],
    '#FF8200': [5.50, 7.50],
    '#EF3340': [7.50, 10.50],
    '#9063CD': [10.50, 15],
    }

dict_rischio = {
    '#97D700': 'Basso',
    '#FCE300': 'Moderato',
    '#FF8200': 'Alto',
    '#EF3340': 'Molto alto',
    # '#9063CD': 'Estremo,
    }


for stazione in dizionario_df.keys():
    cartella_plot = f"plot/{stazione}/{adesso_timestamp.strftime('%Y/%m/%d')}"
    os.makedirs(cartella_plot, exist_ok=True)
    
    df = dizionario_df[stazione]
    df = df.fillna(0)
    nome = df.iloc[0]['NAME']
    df = df[['UV_MEDIA', 'UV_MASSIMA']]
    
    ##############
    
    fig, ax = plt.subplots(figsize=(10, 5))
    
    filigrana = mpimg.imread(os.path.join(cartella_lavoro, 'filigrana.png'))
    aspect_filigrana = 0.8
    
    xlim_fil = (gg3_ts + pd.Timedelta(minutes=90), x_max_asse_ts - pd.Timedelta(minutes=90))
    ylim_fil = (0, 9.5)
    
    larghezza_assi = mdates.date2num(xlim_fil[1]) - mdates.date2num(xlim_fil[0])
    altezza_assi = ylim_fil[1] - ylim_fil[0]
    aspect_assi = larghezza_assi / altezza_assi
    
    if aspect_filigrana > aspect_assi:
        larghezza_fil = larghezza_assi
        altezza_fil = larghezza_assi / aspect_filigrana
    else:
        altezza_fil = altezza_assi
        larghezza_fil = altezza_assi * aspect_filigrana
    
    x_centro = mdates.date2num(xlim_fil[0]) + larghezza_assi / 2
    y_centro = ylim_fil[0] + altezza_assi / 2
    
    ax.imshow(
        filigrana,
        extent=[
            x_centro - larghezza_fil / 2, x_centro + larghezza_fil / 2,
            y_centro - altezza_fil / 2, y_centro + altezza_fil / 2
            ],
        aspect='auto', alpha=0.1, zorder=-200
        )
    
    x_smooth_totale = []
    y_smooth_totale = []
    primo_blocco_max = True
    
    id_blocco = (df['UV_MEDIA'] == 0).cumsum()
    for _, blocco in df[df['UV_MEDIA'] > 0].groupby(id_blocco):
        if len(blocco) < 3:
            continue
        x_num = mdates.date2num(blocco.index)
        y = blocco['UV_MEDIA'].values
        y_max = blocco['UV_MASSIMA'].values
        
        grado = min(3, len(blocco) - 1)
        spline = make_interp_spline(x_num, y, k=grado)
        x_smooth = np.linspace(x_num.min(), x_num.max(), len(blocco) * 10)
        y_smooth = np.clip(spline(x_smooth), 0, None)
        
        spline_max = make_interp_spline(x_num, y_max, k=grado)
        y_smooth_max = np.clip(spline_max(x_smooth), 0, None)
        
        x_smooth_totale.append(x_smooth)
        y_smooth_totale.append(y_smooth)
        
        punti = np.array([x_smooth, y_smooth]).T.reshape(-1, 1, 2)
        segmenti = np.concatenate([punti[:-1], punti[1:]], axis=1)
        colori_segmenti = [get_colore(v, dict_colori) for v in y_smooth[:-1]]
        
        for i in range(len(x_smooth) - 1):
            colore_medio = get_colore((y_smooth[i] + y_smooth[i + 1]) / 2, dict_colori)
            ax.fill_between(
                x_smooth[i:i + 2], y_smooth[i:i + 2], 0,
                color=colore_medio, alpha=1, zorder=5,
                edgecolor='none', linewidth=0, antialiased=False
                )
        
        lc = LineCollection(segmenti, colors=colori_segmenti, linewidth=0, zorder=10)
        ax.add_collection(lc)
        
        if plot_uvmax:
            ax.plot(
                x_smooth, y_smooth_max,
                color='black', linewidth=spessore_uvmax, zorder=15,
                label='UVI max' if primo_blocco_max else None
                )
            
        primo_blocco_max = False
    
    x_smooth_totale = np.concatenate(x_smooth_totale) if x_smooth_totale else np.array([])
    y_smooth_totale = np.concatenate(y_smooth_totale) if y_smooth_totale else np.array([])
    
    y_legenda = 0.97
    x_legenda = 0.02
    
    ax.plot(
        [x_legenda, x_legenda + 0.02], [y_legenda, y_legenda],
        color='black', linewidth=1, transform=ax.transAxes,
        clip_on=False, zorder=300
        )
    ax.text(
        x_legenda + 0.03, y_legenda, 'UVI max',
        transform=ax.transAxes, ha='left', va='center',
        fontsize=7, color='black', clip_on=False, zorder=300
        )
    x_legenda += 0.09 # per rendere più spaziati UVI e Basso
    
    for colore, label in dict_rischio.items():
        txt_legenda = ax.text(
            x_legenda, y_legenda, label,
            transform=ax.transAxes, ha='left', va='center',
            fontsize=7, color='black', fontweight='bold',
            clip_on=False, zorder=300,
            bbox=dict(boxstyle='round,pad=0.3', facecolor=colore, edgecolor='none')
            )
        fig.canvas.draw()
        bbox_legenda = txt_legenda.get_bbox_patch().get_window_extent(renderer=fig.canvas.get_renderer())
        bbox_legenda_axes = bbox_legenda.transformed(ax.transAxes.inverted())
        x_legenda = bbox_legenda_axes.x1 + 0.015
    
    ######################
    
    for colore, valori in list(dict_colori.items())[1:]:
        ax.axhline(y=valori[0], color=colore, linestyle='--', linewidth=0.8, zorder=-10, alpha=0.9)
    
    ax.set_xlabel('')
    ax.set_ylabel('Indice UV')
    ax.set_title(nome)
    ax.margins(x=0)
    ax.set_xlim(gg3_ts, x_max_asse_ts)
    
    #############
    
    ax.set_ylim(0, 9.5)
    ax.set_yticks(range(1, 10))
    ax.tick_params(axis='x', labelsize=8)
    
    ax.xaxis.set_major_locator(mdates.HourLocator(byhour=range(0, 24, 3)))
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(formatta_tick))
    
    fig.canvas.draw()
    xlim_max = ax.get_xlim()[1]
    ultima_label_visibile = None
    for tick_pos, label in zip(ax.get_xticks(), ax.get_xticklabels()):
        if tick_pos <= xlim_max:
            ultima_label_visibile = label
    if ultima_label_visibile is not None:
        ultima_label_visibile.set_visible(False)
    
    ax.grid(axis='y', linestyle='--', alpha=0.2, linewidth=0.6, zorder=-10)
    ax.grid(axis='x', which='major', linestyle='-', alpha=0.1, linewidth=0.6, zorder=-10)
    
    for xc in [gg3_ts + pd.Timedelta(days=1), gg3_ts + pd.Timedelta(days=2)]:
        ax.axvline(x=xc, color='gray', linestyle='-', linewidth=0.6, alpha=0.4, zorder=-100)
    
    plt.tight_layout()
    
    ################
    
    logo = mpimg.imread(os.path.join(cartella_lavoro, 'arpal.png'))
    imagebox = OffsetImage(logo, zoom=0.25)
    ab = AnnotationBbox(
        imagebox,
        (0.99, 0.99),
        xycoords='axes fraction',
        frameon=True,
        box_alignment=(1, 1),
        bboxprops=dict(facecolor='white', edgecolor='none', alpha=0.8)
        )
    ax.add_artist(ab)
    
    def valore_curva(x):
        if len(x_smooth_totale) == 0:
            return np.zeros_like(np.atleast_1d(x), dtype=float)
        return np.interp(x, x_smooth_totale, y_smooth_totale, left=0, right=0)
    
    giorni_finestra = [gg3_ts + pd.Timedelta(days=i) for i in range(3)]
    
    massimi_giorno = []
    for giorno_ts in giorni_finestra:
        giorno = giorno_ts.date()
        gruppo_giorno = df[df.index.date == giorno]
        if len(gruppo_giorno) == 0 or gruppo_giorno['UV_MEDIA'].max() == 0:
            continue
        
        val_max = gruppo_giorno['UV_MEDIA'].max()
        x_pos = giorno_ts + pd.Timedelta(hours=13)
        
        val_locale = valore_curva(np.array([mdates.date2num(x_pos)]))[0]
        massimi_giorno.append((mdates.date2num(x_pos), val_max, val_locale))
        
    x_min_asse, x_max_asse = mdates.date2num(gg3_ts), mdates.date2num(x_max_asse_ts)
    pad_dati = (x_max_asse - x_min_asse) * 0.035
    x_mezzanotti = mdates.date2num([gg3_ts + pd.Timedelta(days=1), gg3_ts + pd.Timedelta(days=2)])
    
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    
    testi_box = []
    for x_pos, val_max, val_locale in massimi_giorno:
        y_box = max(7.15, val_locale + 0.5)
        colore_box = get_colore(val_max, dict_colori)
        txt = ax.text(
            x_pos, y_box, int(np.round(val_max)),
            fontsize=10, fontweight='bold', zorder=200,
            ha='center', va='center_baseline', color='black',
            bbox=dict(boxstyle='round,pad=0.3', facecolor=colore_box, edgecolor='none')
            )
        testi_box.append((txt, x_pos))
    
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    
    for txt, x_pos in testi_box:
        bbox_patch = txt.get_bbox_patch()
        bbox_dati = bbox_patch.get_window_extent(renderer=renderer).transformed(ax.transData.inverted())
        larghezza_box = bbox_dati.x1 - bbox_dati.x0
        
        x_finale = x_pos
        if bbox_dati.x1 > x_max_asse:
            x_finale = x_max_asse - larghezza_box - pad_dati
        elif bbox_dati.x0 < x_min_asse:
            x_finale = x_min_asse + pad_dati
        
        for xm in x_mezzanotti:
            if x_finale < xm < x_finale + larghezza_box:
                x_finale = xm + pad_dati * 0.3
                break
        
        maschera_box = (x_smooth_totale >= x_finale) & (x_smooth_totale <= x_finale + larghezza_box)
        if maschera_box.any():
            max_curva_box = y_smooth_totale[maschera_box].max()
        else:
            max_curva_box = valore_curva(np.array([x_finale, x_finale + larghezza_box])).max()
        y_box = max(7.15, max_curva_box + 0.5)
        
        txt.set_position((x_finale, y_box))
    
    for spine in ax.spines.values():
        spine.set_zorder(200)
        
    percorso_plot = f"{cartella_plot}/{adesso_timestamp.strftime('%Y-%m-%d_%H%M')}.png"
    plt.savefig(percorso_plot, dpi=300, bbox_inches='tight')
    os.system(f'convert {percorso_plot} -strip -colors 32 PNG8:{percorso_plot}')
    
    # plt.show()
    plt.close()
    
    # sss

print('\n\nDone.')
