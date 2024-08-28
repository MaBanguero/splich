import cv2
from pysrt import open as open_srt

def get_text_size(text, font, font_scale, thickness):
    size = cv2.getTextSize(text, font, font_scale, thickness)[0]
    return size

def split_text(text, max_width, font, font_scale, thickness):
    words = text.split()
    line1, line2 = "", ""

    for word in words:
        if get_text_size(line1 + word, font, font_scale, thickness)[0] <= max_width:
            line1 += word + " "
        else:
            if get_text_size(line2 + word, font, font_scale, thickness)[0] <= max_width:
                line2 += word + " "

    return line1.strip(), line2.strip()

def draw_background(frame, line1, line2, font, font_scale, thickness, elapsed_ratio, text_positions):
    words_line1 = line1.split()
    words_line2 = line2.split()

    total_words = len(words_line1) + len(words_line2)
    word_index = int(elapsed_ratio * total_words)

    if word_index < len(words_line1):
        word = words_line1[word_index]
        x, y = text_positions[0]
        for w in words_line1[:word_index]:
            x += get_text_size(w, font, font_scale, thickness)[0] + 20
    else:
        word = words_line2[word_index - len(words_line1)]
        x, y = text_positions[1]
        for w in words_line2[:word_index - len(words_line1)]:
            x += get_text_size(w, font, font_scale, thickness)[0] + 20

    word_size = get_text_size(word, font, font_scale, thickness)
    end_x = x + word_size[0]
    cv2.rectangle(frame, (x - 5, y - word_size[1] - 10), (end_x + 5, y + 10), (128, 0, 128), -1)
    cv2.putText(frame, word, (x, y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

def calculate_text_positions(frame_width, frame_height, line1, line2, font, font_scale, thickness):
    text_size_line1 = get_text_size(line1, font, font_scale, thickness)
    text_size_line2 = get_text_size(line2, font, font_scale, thickness)
    text_x_line1 = (frame_width - text_size_line1[0]) // 2
    text_x_line2 = (frame_width - text_size_line2[0]) // 2
    text_y_line1 = (frame_height + text_size_line1[1]) // 2 - 30
    text_y_line2 = (frame_height + text_size_line1[1]) // 2 + 20
    return [(text_x_line1, text_y_line1), (text_x_line2, text_y_line2)]

def add_subtitles(get_frame, t, subtitles):
    frame = get_frame(t)
    frame_cv2 = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    frame_height, frame_width, _ = frame_cv2.shape
    margin = int(frame_width * 0.1)
    safe_width = frame_width - 2 * margin
    elapsed_ratio = (t % 2) / 2

    for subtitle in subtitles:
        if subtitle.start.ordinal <= t * 1000 < subtitle.end.ordinal:
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 1.6
            thickness = 3
            line1, line2 = split_text(subtitle.text, safe_width, font, font_scale, thickness)
            text_positions = calculate_text_positions(frame_width, frame_height, line1, line2, font, font_scale, thickness)
            draw_background(frame_cv2, line1, line2, font, font_scale, thickness, elapsed_ratio, text_positions)
            draw_remaining_text(frame_cv2, line1, line2, font, font_scale, thickness, text_positions)
            break

    return cv2.cvtColor(frame_cv2, cv2.COLOR_BGR2RGB)

def draw_remaining_text(frame_cv2, line1, line2, font, font_scale, thickness, text_positions):
    x = text_positions[0][0]
    for word in line1.split():
        cv2.putText(frame_cv2, word, (x, text_positions[0][1]), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
        x += get_text_size(word, font, font_scale, thickness)[0] + 20

    x = text_positions[1][0]
    for word in line2.split():
        cv2.putText(frame_cv2, word, (x, text_positions[1][1]), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
        x += get_text_size(word, font, font_scale, thickness)[0] + 20
