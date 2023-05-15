import argparse
import logging
import os
import os.path
import random
import re
import sys
import subprocess
import string


class VideoDustingException(Exception):
    pass

def timestamp_str_to_seconds(timestamp_str):
    current_timestamp_splitted = [int(i) for i in timestamp_str.split(':')]
    if len(current_timestamp_splitted) == 2:
        current_timestamp_splitted.insert(0, 0)
    return sum([current_timestamp_splitted[i] * [3600, 60, 1][i] for i in range(3)])

def seconds_to_timestamp_str(seconds):
    seconds = int(seconds)
    ret_val = ''
    for i in range(3):
        new_number = seconds // [3600, 60, 1][i]
        ret_val += f'{new_number:02}' + ':'
        seconds -= new_number * [3600, 60, 1][i]
    return ret_val[:-1]

def get_output_video_file_path(video_file_path):
    return ''.join(video_file_path.split('.')[:-1]) + '-postprocessing' + '.' + video_file_path.split('.')[-1]

def validate_video(video_file_path):
    if not video_file_path.endswith('.mkv'):
        raise VideoDustingException('Error: Only .mkv video have currently been tested.')

def validate_output_video(video_file_path):
    output_filename = get_output_video_file_path(video_file_path)
    if os.path.exists(output_filename):
        raise VideoDustingException('Error: Output file already exists: ' + output_filename)

def validate_dusting_rules(rules_file_path):
    dusting_rules = []
    last_timestamp = -1
    with open(rules_file_path, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith('#') or line == "":
                continue  # Possibility to have blank lines or commented lines
            regex = r"^((?:\d+[\:\.]){1,2}\d+)\s*\=\s*(.*)$"
            matches = re.findall(regex, line)
            if len(matches) != 1:
                raise VideoDustingException('Error: Bad format in ' + rules_file_path + ' at line: ' + line)
            dusting_rules.append({'timestamp':matches[0][0],'value':matches[0][1]})

            # Check that timestamps are be monotonically increasing
            current_timestamp = timestamp_str_to_seconds(dusting_rules[-1]['timestamp'])
            if current_timestamp <= last_timestamp:
                raise VideoDustingException('Error: The timestamps must be monotonically increasing: ' + dusting_rules[-1]['timestamp'])
            last_timestamp = current_timestamp
    return dusting_rules

def analyze_dusting_rules(video_file_path, dusting_rules):
    # Executing:
    # ffprobe -select_streams v -skip_frame nokey -show_frames -show_entries frame=pkt_pts_time
    command = 'ffprobe -select_streams v -skip_frame nokey -show_frames -show_entries frame=pkt_pts_time'.split(' ')
    command.append(video_file_path)
    logging.info('Running ffprobe: ' + str(command))
    p = subprocess.run(command, capture_output=True)
    if p.returncode != 0:
        raise VideoDustingException('Error: Internal error when running ffprobe')
    
    # Processing ffprobe output. Interesting lines format is 'pkt_pts_time=3763.000000'
    regex = r"pkt_pts_time\=(\d+\.\d+)"
    matches = re.findall(regex, p.stdout.decode())
    keyframe_timestamps = [float(keyframe_timestamp_str) for keyframe_timestamp_str in matches]
    
    # uts = user timestamp
    # kfts = keyframe timestamp
    for rule in dusting_rules:
        uts_str = rule['timestamp']
        uts = float(timestamp_str_to_seconds(rule['timestamp']))
        for j in range(len(keyframe_timestamps)):
            kfts = keyframe_timestamps[j]
            if uts == kfts:
                break
            else:
                if uts < kfts and j == 0:
                    print('For ' + uts_str + ': First keyframe is at: ' + seconds_to_timestamp_str(keyframe_timestamps[j]))
                    break
                if uts < kfts:
                    print('For ' + uts_str + ': Closest keyframes: ' + seconds_to_timestamp_str(keyframe_timestamps[j-1]) + '..' + seconds_to_timestamp_str(keyframe_timestamps[j]) + ' - ' + rule['value'])
                    break
                if uts > kfts and j == len(keyframe_timestamps) - 1:
                    print('For ' + uts_str + ': Latest keyframe is at: ' + seconds_to_timestamp_str(keyframe_timestamps[j]))
                    break

def get_chapters(dusting_rules):
    chapters = []
    for rule in dusting_rules:
        if rule['value'].lower() != 'cut':
            chapters.append({'timestamp':rule['timestamp'],'title':rule['value']})
    return chapters

def get_periods_to_keep(dusting_rules):
    periods_to_keep = []
    a_sequence_is_ongoing = False
    for rule in dusting_rules:
        if rule['value'].lower() == 'cut':
            if a_sequence_is_ongoing:
                periods_to_keep[-1].append(rule['timestamp'])
                a_sequence_is_ongoing = False
        else:
            if not a_sequence_is_ongoing:
                periods_to_keep.append([rule['timestamp']])
                a_sequence_is_ongoing = True
    return periods_to_keep

def periods_to_keep_as_string(periods_to_keep):
    periods_to_keep_as_str = ""
    for period in periods_to_keep:
        start = period.pop(0)
        if start != "00:00:00":
            periods_to_keep_as_str += start
        periods_to_keep_as_str += '-'
        try:
            stop = period.pop()
            periods_to_keep_as_str += stop
        except IndexError:  # No stop
            pass
        periods_to_keep_as_str += ',+'
    periods_to_keep_as_str = periods_to_keep_as_str[:-2]
    return periods_to_keep_as_str

def create_command(video_file_path, chapters_filename, periods_to_keep):
    command = [ 'mkvmerge' ]

    if os.path.exists(chapters_filename):
        chapters_options = [
            '--chapters',
            chapters_filename
        ]
        command += chapters_options

    if len(periods_to_keep) > 0:
        split_options = [
            '--split',
            'parts:' + periods_to_keep_as_string(periods_to_keep)
        ]
        command += split_options

    output_options = [
        '-o',
        get_output_video_file_path(video_file_path)
    ]
    command += output_options

    arguments = [ video_file_path ]
    command += arguments

    # If there is nothing to do, return none
    if '--chapters' not in command and '--split' not in command:
        command = None

    return command

def main(video_file_path, rules_file_path, dry_run):
    validate_video(video_file_path)
    validate_output_video(video_file_path)
    dusting_rules = validate_dusting_rules(rules_file_path)

    # Requesting user confirmation
    if dry_run:
        analyze_dusting_rules(video_file_path, dusting_rules)

    # Computing the chapters
    chapters = get_chapters(dusting_rules)
    logging.info('Chapters: ' + str(chapters))

    # Write chapters to a temporary file
    chapters_filename_length = 16
    chapters_filename = 'zz' + ''.join(random.choice(string.ascii_lowercase) for i in range(chapters_filename_length))
    if len(chapters) > 0:
        with open(chapters_filename, 'w') as f:
            for i in range(len(chapters)):
                chapter = chapters[i]
                f.write('CHAPTER' + f"{i:02d}" + '=' + chapter['timestamp'] + '.000' + '\n')
                f.write('CHAPTER' + f"{i:02d}" + 'NAME' + '=' + chapter['title'] + '\n')
        logging.info('Temporary chapters file saved: ' + chapters_filename)

    # Computing the periods to keep
    periods_to_keep = get_periods_to_keep(dusting_rules)
    logging.info('Periods to keep: ' + str(periods_to_keep))
    
    # Creating the command to run
    # Example:
    #   command = "mkvmerge --chapters dev/chapters.d --split parts:00:00:06-00:00:16,+00:00:26-00:00:36 -o toto.mkv dev/2023-05-12_13-50-15.mkv"
    command = create_command(video_file_path, chapters_filename, periods_to_keep)

    if command is None:
        raise VideoDustingException('Error: No rules to apply')
    else:
        if dry_run:
            logging.info('Running (but not executed as in dry-run mode): ' + ' '.join(command))
        else:
            logging.info('Running: ' + ' '.join(command))
            p = subprocess.run(command)
            if p.returncode != 0:
                raise VideoDustingException('Error: Internal error when running mkvmerge')

    # Remove the chapters temporary file
    if os.path.exists(chapters_filename):
        #os.remove(chapters_filename)
        logging.info('Temporary chapters file deleted: ' + chapters_filename)


if __name__ == '__main__':

    parser = argparse.ArgumentParser(
                    prog='Viddusting',
                    description='Allows to cut sequences and create chapters in a video from a simple description as file')

    parser.add_argument('-v', '--verbose',
                        action='store_true')
    parser.add_argument('-y', '--yes',
                        action='store_true')
    parser.add_argument('--dry-run',
                        action='store_true')
    parser.add_argument('-r', '--rules')
    parser.add_argument('video_file_path')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    video_file_path = r'{}'.format(args.video_file_path)  # raw string to better manage space in strings from user.
    if not os.path.exists(args.video_file_path):
        sys.exit('Error: Video not found: ' + video_file_path)

    rules_file_path = args.rules
    if rules_file_path is None:
        # If dusting_rules is not provided, assumption is made from the video base name + '.vdr' 
        rules_file_path = '.'.join(video_file_path.split('.')[:-1]) + '.vdr'
    if not os.path.exists(rules_file_path):
        sys.exit('Error: Dusting rules not found: ' + rules_file_path)

    # Run the main process
    try:
        main(video_file_path, rules_file_path, args.dry_run)
    except VideoDustingException as e:
        sys.exit(e)