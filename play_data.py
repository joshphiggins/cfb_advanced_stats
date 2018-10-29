import requests
import logging
import pandas as pd
import numpy as np
from IPython.display import display


logger = logging.getLogger(__name__)


def get_ppp():
    points = np.array([(16, 1), (48, 2), (64, 3), (82, 4),
                       (92, 5), (98, 6), (100, 7)])
    x = points[:, 0]
    y = points[:, 1]
    z = np.polyfit(x, y, 3)
    f = np.poly1d(z)
    x_new = np.linspace(x[0], x[-1], 100)
    y_new = f(x_new)
    return y_new




def get_json_data(game_id):
    response = requests.get(
        'http://cdn.espn.com/core/college-football/playbyplay?gameId={}&xhr=1&render=false&userab=18'.format(game_id))
    data = response.json()
    return data


def get_team_data(data):
    u_dict = {}
    away = {
        "displayName": data['__gamepackage__']['awayTeam']['team']['displayName'],
        "abv": data['__gamepackage__']
                ['awayTeam']['team']['abbreviation']}

    home = {
        "displayName": data['__gamepackage__']['homeTeam']['team']['displayName'],
        "abv": data['__gamepackage__']
                ['homeTeam']['team']['abbreviation']}

    u_dict['awayTeam'] = away
    u_dict['homeTeam'] = home

    return u_dict


def get_clean_play_data(drive_data, awayTeam, homeTeam, possTeam):
    drive_list = []
    for d in drive_data:
        u_dict = {}
        home_score = "{}_score".format(homeTeam)
        away_score = "{}_score".format(awayTeam)
        u_dict[home_score] = d['homeScore']
        u_dict[away_score] = d['awayScore']
        u_dict['quarter'] = d['period']['number']
        u_dict['clock'] = d['clock']['displayValue']
        u_dict['endDown'] = d['end']['down']
        u_dict['endDistance'] = d['end']['distance']
        u_dict['possession'] = possTeam
        if 'startDownDistanceText' in d['end'].keys():
            u_dict['endDownDistanceText'] = d['end']['shortDownDistanceText']
        if 'possessionText' in d['end'].keys():
            u_dict['endPossessionText'] = d['end']['possessionText']
        u_dict['endYardLine'] = d['end']['yardLine']
        u_dict['endYardsToEndzone'] = d['end']['yardsToEndzone']
        u_dict['text'] = d['text']
        u_dict['statYardage'] = d['statYardage']
        if 'abbreviation' in d['type'].keys():
            type_abv = d['type']['abbreviation']
            type_text = d['type']['text']
            u_dict['type_abv'] = get_td_play_type(type_abv, type_text)
        elif 'text' in d['type'].keys():
            u_dict['type_abv'] = d['type']['text']
        if 'text' in d['type'].keys():
            u_dict['type_text'] = d['type']['text']
        u_dict['startDown'] = d['start']['down']
        u_dict['startDistance'] = d['start']['distance']
        if 'shortDownDistanceText' in d['start'].keys():
            u_dict['startDownDistanceText'] = d['start']['shortDownDistanceText']
        if 'possessionText' in d['start'].keys():
            u_dict['startPossessionText'] = d['start']['possessionText']
        u_dict['startYardLine'] = d['start']['yardLine']
        u_dict['startYardsToEndzone'] = d['start']['yardsToEndzone']
        u_dict['scoringPlay'] = d['scoringPlay']
        drive_list.append(u_dict)
    return drive_list


def get_td_play_type(type_abv, type_text):
    if type_abv == 'TD':
        if type_text.split()[0] == 'Passing':
            return 'REC'
        elif type_text.split()[0] == 'Rushing':
            return 'RUSH'
    if type_abv is None or np.isnan(type_abv):
        return type_text
    return type_abv

def clean_all_drives(json, awayTeam, homeTeam):
    data = json['gamepackageJSON']['drives']
    if 'previous' in data.keys() and 'current' in data.keys():
        play_by_play = []
        cur_drives = data['current']
        for d in cur_drives:
            possTeam = d['team']['abbreviation']
            clean_drives = get_clean_play_data(
                d['plays'], awayTeam, homeTeam, possTeam)
            play_by_play = play_by_play + clean_drives

        prev_drives = data['previous']
        for d in prev_drives:
            possTeam = d['team']['abbreviation']
            clean_drives = get_clean_play_data(d['plays'], awayTeam, homeTeam, possTeam)
            play_by_play = play_by_play + clean_drives

        return play_by_play
    elif 'previous' in data.keys():
        drives = data['previous']
        play_by_play = []
        for d in drives:
            possTeam = d['team']['abbreviation']
            clean_drives = get_clean_play_data(d['plays'], awayTeam, homeTeam, possTeam)
            play_by_play = play_by_play + clean_drives
        return play_by_play
    logger.error("No drives found")

def success_rate_bool(statYardage, startDown, startDistance, type_abv):
    if type_abv == "REC" or type_abv == "RUSH" or type_abv == "Fumble Recovery (Own)":
        if startDown == 1:
            suc_yards = startDistance / 2
        elif startDown == 2:
            suc_yards = startDistance * 0.7
        else:
            suc_yards = startDistance

        if statYardage >= suc_yards:
            return True
        return False
    elif type_abv == "INTR":
        return False
    elif type_abv == 'Pass Incompletion':
        return False
    elif type_abv == 'Sack':
        return False
    elif type_abv == 'Fumble Recovery (Opponent)':
        return False

    return np.nan

def garbage_time_calc(homeScore, awayScore, quarter):
    score_margin = abs(homeScore - awayScore)
    if quarter == 2 and score_margin > 38:
        return True
    elif quarter == 3 and score_margin > 28:
        return True
    elif quarter == 4 and score_margin > 22:
        return True
    return False

def line_yards_calc(type_abv, statYardage):
    if type_abv == "RUSH":
        if statYardage < 0:
            lineYards = statYardage * 1.25
        elif statYardage < 4:
            lineYards = statYardage
        elif statYardage < 7:
            midYards = (statYardage - 6) / 2
            lineYards = 3 + midYards
        else:
            lineYards = 5
        return lineYards
    return 0


def hlt_yards_calc(type_abv, line_yards, statYardage):
    if type_abv == "RUSH":
        if statYardage < 0:
            hltYards = 0
        hltYards = statYardage - line_yards
        return hltYards
    return 0


def stuff_rt_calc(type_abv, statYardage):
    if type_abv == "RUSH":
        if statYardage < 0:
            return True
        return False
    return False

def down_type_calc(down, distance):
    if down == 1:
        return 'STD'
    elif down == 2 and distance < 8:
        return 'STD'
    elif down == 3 or down == 4 and distance < 5:
        return 'STD'
    return 'PASS'


def calc_ppp(statYardage):
    global ppp_list
    if statYardage < 0:
        index = abs(statYardage) + 1
        return - ppp_list[index]
    return ppp_list[statYardage + 1]

def add_adv_stats(df, away_abv, home_abv):
    df['successPlay'] = df.apply(
        lambda row: success_rate_bool(
            row['statYardage'], row['startDown'], row['startDistance'], row['type_abv']
        ), axis=1)

    homeScore = "{}_score".format(home_abv)
    awayScore = "{}_score".format(away_abv)

    df['garbageBool'] = df.apply(
        lambda row: garbage_time_calc(row[homeScore], row[awayScore], row['quarter']), axis=1
    )

    df['lineYards'] = df.apply(
        lambda row: line_yards_calc(row['type_abv'], row['statYardage']), axis=1
    )

    df['highlightYards'] = df.apply(
        lambda row: hlt_yards_calc(row['type_abv'], row['lineYards'], row['statYardage']), axis=1
    )

    df['stuffRate'] = df.apply(
        lambda row: stuff_rt_calc(row['type_abv'], row['statYardage']), axis=1
    )

    df['downType'] = df.apply(
        lambda row: down_type_calc(row['startDown'], row['startDistance']), axis=1
    )
    ppp_list = get_ppp()

    df['PPP'] = df.apply(
        lambda row: ppp[row['statYardage'] + 1 ], axis=1
    )
    return df

def make_df(gameId):
    json_data = get_json_data(gameId)
    team_dict = get_team_data(json_data)
    away_abv = team_dict['awayTeam']['abv']
    home_abv = team_dict['homeTeam']['abv']
    all_play_by_play = clean_all_drives(json_data, away_abv, home_abv)

    df = pd.DataFrame(all_play_by_play)
    df = add_adv_stats(df, away_abv, home_abv)

    return df


def suc_by_qtr(df):
    return df.groupby(['possession', 'quarter'])['successPlay'].apply(lambda x: x[x == True].count() / x.count())

def suc_overall(df):
    return df.groupby(['possession'])['successPlay'].apply(lambda x: x[x == True].count() / x.count())

def suc_down_type(df):
    return df.groupby(['possession', 'downType'])['successPlay'].apply(lambda x: x[x == True].count() / x.count())

def suc_play_type(df):
    return df.groupby(['possession', 'type_abv'])['successPlay'].apply(lambda x: x[x == True].count() / x.count())

def suc_by_down(df):
    return df[(df.startDown > 0) & (df.startDown < 4)].groupby(['possession', 'startDown'])['successPlay'].apply(lambda x: x[x == True].count() / x.count())


def frames_to_diplay(df):
    print("--------- SUCCESS RATE START ----------")
    print('-------- OVERALL SUCCESS RATE ---------')
    display(
        df[df['garbageBool'] == False].groupby(['possession'])['successPlay'].apply(
        lambda x: x[x == True].count() / x.count()).to_frame()
    )
    print("------- SUCCESS RATE BY QTR ------------")
    display(
        df[df['garbageBool'] == False].groupby(['possession', 'quarter'])['successPlay'].apply(
        lambda x: x[x == True].count() / x.count()).to_frame()
    )
    print("-------- SUCCESS RATE BY DOWN ------------")
    display(
        df[df['garbageBool'] == False].groupby(['possession', 'downType'])['successPlay'].apply(
        lambda x: x[x == True].count() / x.count()).to_frame()
    )

    print("-------- SUCCESS RATE BY PLAY TYPE ------------")
    display(
        df[
            (df['garbageBool'] == False) &
            (df['type_abv'] == "RUSH") |
            (df['type_abv'] == "REC")
        ].groupby(['possession', 'downType'])['successPlay'].apply(
        lambda x: x[x == True].count() / x.count()).to_frame()
    )

    print("-----------SUCCESS RATE END ----------")
    print("--------EXPLOSIVE PLAYS START ------------")
    print("-------- RUSH PLAYS > 10 YARDS -----------")
    display(
        df[
            (df['successPlay'] == True) &
            (df['garbageBool'] == False) &
            (df['statYardage'] > 10) &
            (df['type_abv'] == 'RUSH')
        ].groupby('possession')['statYardage'].count().to_frame()
    )

    print("--------- PASS PLAYS > 20 YARDS ---------------")
    display(
        df[
            (df['successPlay'] == True) &
            (df['garbageBool'] == False) &
            (df['statYardage'] > 20) &
            (df['type_abv'] == 'REC')
        ].groupby('possession')['statYardage'].count().to_frame()
    )

    print("-------- AVG YARDS ON SUC PLAYS ---------------")
    display(
        df[
            (df['successPlay'] == True) &
            (df['garbageBool'] == False)
        ].groupby('possession')['statYardage'].mean().to_frame()
    )

    print("--------EXPLOSIVE PLAYS END ------------")
    print("---------- LINE YARDS AVG OVERALL --------------")
    display(
        df[
            (df['successPlay'] == True) &
            (df['type_abv'] == 'RUSH')
        ].groupby(['possession'])['lineYards'].mean().to_frame()
    )

    print("---------- LINE YARDS AVG BY QTR --------------")
    display(
        df[
            (df['successPlay'] == True) &
            (df['type_abv'] == 'RUSH')
        ].groupby(['possession', 'quarter'])['lineYards'].mean().to_frame()
    )

    print("----------- HIGHLIGHT YARDS AVG OVERALL ------------")
    display(
        df[
            (df['successPlay'] == True) &
            (df['type_abv'] == 'RUSH')
        ].groupby(['possession'])['highlightYards'].mean().to_frame()
    )

    print("---------- HIGHLIGHT YARDS AVG BY QTR --------------")
    display(
        df[
            (df['successPlay'] == True) &
            (df['type_abv'] == 'RUSH')
        ].groupby(['possession', 'quarter'])['highlightYards'].mean().to_frame()
    )
