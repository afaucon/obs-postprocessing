import os
import os.path
import random
import re
import sys
import subprocess
import string


def validate_dusting_rules(dusting_rules):
    descriptor = []
    last_timestamp = -1
    with open(dusting_rules, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith('#') or line == "":
                continue  # Possibility to have blank lines or commented lines
            regex = r"^((?:\d+[\:\.]){1,2}\d+)\s*\=\s*(.*)$"
            matches = re.findall(regex, line)
            if len(matches) != 1:
                sys.exit('Format error in ' + dusting_rules + ' at line: ' + line)
            descriptor.append({'timestamp':matches[0][0],'value':matches[0][1]})

            # Check that timestamps are be monotonically increasing
            current_timestamp_splitted = [int(i) for i in descriptor[-1]['timestamp'].split(':')]
            if len(current_timestamp_splitted) == 2:
                current_timestamp_splitted.insert(0, '00')
            multiplicator = [3600, 60, 1]
            current_timestamp = 0
            for i in range(len(multiplicator)):
                current_timestamp += current_timestamp + current_timestamp_splitted[i] * multiplicator[i]
            if current_timestamp <= last_timestamp:
                sys.exit('The timestamps must be monotonically increasing: ' + current_timestamp)
            last_timestamp = current_timestamp
    return descriptor

def validate_video(video):
    if not video.endswith('.mkv'):
        sys.exit('Only .mkv video have currently been tested.')
    return video

def main(dusting_rules, video):
    descriptor = validate_dusting_rules(dusting_rules)
    video = validate_video(video)

    # Computing the periods to keep
    periods_to_keep = []
    a_sequence_is_ongoing = False
    for desc in descriptor:
        if desc['value'].lower() == 'cut':
            if a_sequence_is_ongoing:
                periods_to_keep[-1].append(desc['timestamp'])
                a_sequence_is_ongoing = False
        else:
            if not a_sequence_is_ongoing:
                periods_to_keep.append([desc['timestamp']])
                a_sequence_is_ongoing = True
    #print(periods_to_keep)

    # Computing the periods to keep as string
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
    #print(periods_to_keep_as_str)

    # Computing the chapters
    chapters = []
    for desc in descriptor:
        if desc['value'].lower() != 'cut':
            chapters.append({'timestamp':desc['timestamp'],'title':desc['value']})
    #print(chapters)

    # Write chapters to a temporary file 
    TEMP_FILENAME_LENTH = 16
    TEMP_FILENAME = 'zz' + ''.join(random.choice(string.ascii_lowercase) for i in range(TEMP_FILENAME_LENTH))
    with open(TEMP_FILENAME, 'w') as f:
        for i in range(len(chapters)):
            chapter = chapters[i]
            f.write('CHAPTER' + f"{i:02d}" + '=' + chapter['timestamp'] + '.000' + '\n')
            f.write('CHAPTER' + f"{i:02d}" + 'NAME' + '=' + chapter['title'] + '\n')

    # Compute output file name based on the input file name
    output_filename = ''.join(video.split('.')[:-1]) + '-postprocessing' + '.' + video.split('.')[-1]

    # Creating the command to run
    # Example:
    #   command = "mkvmerge --chapters dev/chapters.d --split parts:00:00:06-00:00:16,+00:00:26-00:00:36 -o toto.mkv dev/2023-05-12_13-50-15.mkv"
    command = [
        'mkvmerge',
        '--chapters',
        TEMP_FILENAME,
        '--split',
        'parts:' + periods_to_keep_as_str,
        '-o',
        output_filename,
        video
    ]

    #print('Running:')
    #print(' '.join(command))
    #sys.exit('Exitting before running the command')
    subprocess.run(command)

    # Remove the chapters temporary file
    os.remove(TEMP_FILENAME)



if __name__ == '__main__':

    # Extract arguments from command line
    dusting_rules = sys.argv[1]
    video = sys.argv[2]

    if not os.path.exists(dusting_rules):
        sys.exit('File not found: ' + dusting_rules)

    if not os.path.exists(video):
        sys.exit('File not found: ' + video)

    # Run the main process
    main(dusting_rules, video)