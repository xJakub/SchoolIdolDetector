import sys, itertools, requests, json, os.path, hashlib, time, cv2, numpy as np

api_cache_folder = 'cache'
api_url = 'http://schoolido.lu/api/cards/?page_size=100'
round_card_images_folder = 'round_card_images'
all_patterns_file = 'cache/all_patterns.png'

circle_size = 128

rarity_top = 2
rarity_height = 22
rarity_left = 2
rarity_width = 22

pattern_top = 16
pattern_height = 80
pattern_left = 16
pattern_width = 80
pattern_ratio = 0.5

match_top = 12
match_height = 88
match_left = 12
match_width = 88


def api_get(url):
    """
    Make a request against the schoolido.lu api. The results are cached
    :param url: url
    :return: result data
    """
    cache_file = "%s/%s.json" % (api_cache_folder, hashlib.md5(url).hexdigest())
    if not os.path.isfile(cache_file):
        if not os.path.isdir(api_cache_folder):
            os.mkdir(api_cache_folder)
        api_result = []
        while url is not None:
            sys.stderr.write('Fetching %s\n' % url)
            r = requests.get(url)
            if r.status_code != 200:
                raise Exception(r.status_code)
            json_data = r.json()
            url = json_data['next']
            api_result += json_data['results']
        with open(cache_file, 'w') as f:
            json.dump(api_result, f, indent=4, sort_keys=True)

        if os.path.isfile(all_patterns_file):
            os.unlink(all_patterns_file)

    with open(cache_file) as f:
        result = json.load(f)
    return result


def get_card_images(card):
    """
    Returns a list of a card's round images including the remote and local (if cached) paths, and whether it
    belongs to the idolized version of the card
    :param card: card data from schoolido.lu api
    :return: list of (url, local_path, idolized) tuples 
    """
    urls = [(card['round_card_image'], False), (card['round_card_idolized_image'], True)]
    result = []
    for url, idolized in urls:
        if url is None:
            continue
        if url[0:2] == '//':
            url = 'http:%s' % url
        local_path = "%s/%s" % (round_card_images_folder, os.path.basename(url).split('?')[0])
        result.append((url, local_path, idolized))
    return result


def fetch_round_card(card):
    """
    Downloads a card's round images (if they don't exist).
    There is a 100ms sleep time after each download to give the host some rest.
    :param card: card data from schoolido.lu api
    """
    if not os.path.isdir(round_card_images_folder):
        os.mkdir(round_card_images_folder)

    for url, dest, idolized in get_card_images(card):
        if not os.path.isfile(dest):
            sys.stderr.write('Fetching %s\n' % url)
            r = requests.get(url)
            if r.status_code != 200:
                raise Exception(r.status_code)
            with open(dest, 'wb') as f:
                f.write(r.content)
            time.sleep(0.1)


def get_card_group(card, idolized):
    """
    Returns an identifier for a card's group, to help separate them by rarities
    :param card: card data from schoolido.lu api
    :param idolized: True if idolized version
    :return: card group name
    """
    return "%s-%s%d" % (card['rarity'], card['attribute'], 1 if idolized else 0)


def make_rarity_patterns(cards):
    """
    Make and return patterns for each card rarity
    :param cards: list of card data from schoolido.lu ap
    :return: list of (group identifier, pattern, idolized) tuples
    """
    did = {}
    patterns = []

    for card in cards:
        images = get_card_images(card)
        for index, (url, local_path, idolized) in enumerate(images):
            group = get_card_group(card, idolized)
            if group in did:
                continue
            did[group] = 1
            im = cv2.imread(local_path)
            im_cropped = im[rarity_top:rarity_top + rarity_height, rarity_left:rarity_left + rarity_width]
            patterns.append((group, im_cropped, idolized))
    return patterns


def get_pattern_coordinates(index, idolized):
    """
    Returns coordinates for extracting the card's pattern from the all_patterns image  
    :param index: card index inside the cards obtained from the api
    :param idolized: True if idolized version
    :return: coordinates to be used as im_patterns[coordinates]
    """
    real_index = (index * 2 + 1) if idolized else (index * 2)
    y1 = int(pattern_height * pattern_ratio * real_index)
    y2 = int(pattern_height * pattern_ratio * (real_index + 1))
    x1 = 0
    x2 = int(pattern_width * pattern_ratio)
    return np.index_exp[y1:y2, x1:x2]


def generate_all_patterns(cards):
    """
    Generates an all_patterns image
    :param cards: list of card data from schoolido.lu ap
    """
    if not os.path.isdir(os.path.dirname(all_patterns_file)):
        os.mkdir(os.path.dirname(all_patterns_file))
    coordinates = get_pattern_coordinates(len(cards), True)
    im_patterns_height, im_patterns_width = [c.stop for c in coordinates]
    im_patterns = np.ones((im_patterns_height, im_patterns_width, 3), np.uint8)

    for index, card in enumerate(cards):
        for url, local_path, idolized in get_card_images(card):
            if not os.path.exists(local_path):
                fetch_round_card(card)
            im = cv2.imread(local_path)
            im_cropped = im[pattern_top:pattern_top + pattern_height, pattern_left:pattern_left + pattern_width]
            im_cropped = cv2.resize(im_cropped, (0, 0), fx=pattern_ratio, fy=pattern_ratio)
            coordinates = get_pattern_coordinates(index, idolized)
            im_patterns[coordinates] = im_cropped
    cv2.imwrite(all_patterns_file, im_patterns)


def make_card_patterns(cards):
    """
    Return patterns for each round card image
    :param cards: list of card data from schoolido.lu ap
    :return: a map, with group identifiers as keys and a list of (pattern, card data, idolized) as values
    """
    if not os.path.isfile(all_patterns_file):
        generate_all_patterns(cards)

    im_patterns = cv2.imread(all_patterns_file)
    result = {}
    for index, card in enumerate(cards):
        for url, local_path, idolized in get_card_images(card):
            coordinates = get_pattern_coordinates(index, idolized)
            im_cropped = im_patterns[coordinates]

            groups = [get_card_group(card, idolized)]
            # Include non-idolized patterns in both groups, since an idolized card can show the unidolized version
            if not idolized:
                groups.append(get_card_group(card, True))
            for group in groups:
                if group not in result:
                    result[group] = []
                result[group].append((im_cropped, card, idolized))
    return result


def vertical_split(im):
    """
    Split an image vertically. This works for member list as well as (well, most times) scouting screenshots 
    :param im: screenshot data
    :return: the ratio for resizing the screenshot, a list of (start, stop) chunks to use when looping
    """
    im_gray = cv2.cvtColor(im, cv2.COLOR_RGB2GRAY)
    thresh = 223

    im_bw = cv2.threshold(im_gray, thresh, 255, cv2.THRESH_BINARY)[1]
    rows = [y for y in xrange(len(im_bw)) if
            max([len(list(g)) for e, g in itertools.groupby(im_bw[y]) if e == 255] or [0]) > len(im[0]) / 2]

    row_groups = [(min(arr), max(arr)) for arr in np.split(rows, np.where(np.diff(rows) != 1)[0] + 1)]
    row_sizes = [(b[0] - a[1] - 1) for a, b in zip(row_groups, row_groups[1:]) if (b[0] - a[1] - 1) > 100]
    row_positions = [(a[1], b[0]) for a, b in zip(row_groups, row_groups[1:]) if (b[0] - a[1] - 1) > 100]

    ratio = 1.0 * circle_size / np.median(row_sizes)
    return ratio, row_positions


def horizontal_split(im):
    """
    Horizontally split a row into smaller chunks which could contain rounded card images
    :param im: a screenshot's row obtained after using vertical_split's result
    :return: a list of (start, stop) chunks to use when looping
    """
    im_gray = cv2.cvtColor(im, cv2.COLOR_RGB2GRAY)
    thresh = 223

    im_bw = cv2.threshold(im_gray, thresh, 255, cv2.THRESH_BINARY)[1]
    im_width = len(im[0])

    cols = [y for y in xrange(len(im_bw[0])) if 0 not in np.transpose(im_bw)[y]]

    col_groups = [(min(arr), max(arr)) for arr in np.split(cols, np.where(np.diff(cols) != 1)[0] + 1)]
    col_positions = [(b, b + circle_size) for a, b in col_groups] + [(a - circle_size, a) for a, b in col_groups]
    unique_col_positions = []
    for col_position in col_positions:
        if col_position[0] < 0 or col_position[1] >= im_width:
            continue
        if any([abs(col_position[0] - col_position2[0]) <= 2 and abs(col_position[1] - col_position2[1]) <= 2 for
                col_position2 in unique_col_positions]):
            break
        unique_col_positions.append(col_position)

    return unique_col_positions


def get_matching_cards(im_match, possible_cards):
    """
    Tries to match a region against a list of possible card patterns
    :param im_match: region data
    :param possible_cards: list of (card_pattern, card data, idolized) tuples
    :return: the matching cards, as (card data, idolized) tuples
    """
    im_match = cv2.resize(im_match, (0, 0), fx=pattern_ratio, fy=pattern_ratio)
    matches = []
    threshold = 0.8
    for card_pattern, card, idolized in possible_cards:
        if len(im_match) < len(card_pattern) or len(im_match[0]) < len(card_pattern[0]):
            break
        res = cv2.matchTemplate(im_match, card_pattern, cv2.TM_CCOEFF_NORMED)
        loc = np.where(res >= threshold)
        card_pattern_matches = zip(*loc[::-1])
        if card_pattern_matches:
            matches.append((card, idolized))
    return matches


def search_row(im, rarity_patterns, card_patterns):
    """
    Searches a row for round card pattern matches
    :param im: the image's row data
    :param rarity_patterns: result from make_rarity_patterns
    :param card_patterns: result from make_make_card_patterns 
    :return: list of match information
    """
    found_cards = []

    im_width = len(im[0])
    im_height = len(im)

    col_positions = horizontal_split(im)

    for group_min_x, group_max_x in col_positions:
        im4 = im[:, group_min_x:group_max_x]
        found_match = False

        for pattern_group, pattern, pattern_idolized in rarity_patterns:
            if found_match:
                break

            im3 = im4[0:rarity_top + rarity_height + 2, 0:rarity_left + rarity_width + 2]
            res = cv2.matchTemplate(im3, pattern, cv2.TM_CCOEFF_NORMED)

            threshold = 0.7
            loc = np.where(res >= threshold)
            rarity_pattern_matches = zip(*loc[::-1])

            for index, pt in enumerate(rarity_pattern_matches):
                distances = [abs(pt[0] - pt2[0]) + abs(pt[1] - pt2[1]) for pt2 in rarity_pattern_matches[:index]]
                if distances and min(distances) < 100:
                    continue

                match_x = pt[0] - rarity_left
                match_y = pt[1] - rarity_top
                relative_x = 1.0 * (match_x + group_min_x) / im_width
                relative_y = 1.0 * match_y / im_height

                im_match = im4[pt[1] + match_top:pt[1] + match_top + match_height,
                           pt[0] + match_left:pt[0] + match_left + match_width]
                for matching_card, matching_idolized in get_matching_cards(im_match, card_patterns[pattern_group]):
                    found_cards.append({
                        'card': matching_card,
                        'idolized': matching_idolized,
                        'relative_x': relative_x,
                        'relative_y': relative_y,
                    })
                    found_match = True
                    break
    return found_cards


def main():
    """
    Reads a screenshot and tries to find round card image matches, using data and images from schoolido.lu
    The screenshot's path is read from argv[1]
    The result is written as json to stdout
    Extra info is written to stderr
    Note:   Cache is stored inside cache/ and round_card_images/
            Delete the cache/ folder to force downloading of card data
    """
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    start = time.time()
    cards = api_get(api_url)
    sys.stderr.write("%f elapsed after api_get\n" % (time.time() - start))

    card_patterns = make_card_patterns(cards)
    sys.stderr.write("%f elapsed after card_patterns\n" % (time.time() - start))

    rarity_patterns = make_rarity_patterns(cards)
    sys.stderr.write("%f elapsed after rarity_patterns\n" % (time.time() - start))

    im_original = cv2.imread(sys.argv[1])
    sys.stderr.write("%f elapsed after imread\n" % (time.time() - start))

    ratio, row_positions = vertical_split(im_original)
    sys.stderr.write("%f elapsed after vertical_split\n" % (time.time() - start))

    original_width = len(im_original[0])
    original_height = len(im_original)
    resized_width = original_width * ratio
    resized_height = original_height * ratio

    found_cards = []
    for group_min_y, group_max_y in row_positions:
        im = cv2.resize(im_original[group_min_y:group_max_y, :], (0, 0), fx=ratio, fy=ratio)
        group_min_relative_y = 1.0 * group_min_y / original_height
        group_relative_h = 1.0 * (group_max_y - group_min_y) / original_height
        for found_card in search_row(im, rarity_patterns, card_patterns):
            found_card['relative_y'] = group_min_relative_y + group_relative_h * found_card['relative_y']
            found_cards.append(found_card)

    for found_card in found_cards:
        found_card['relative_w'] = 1.0 * circle_size / resized_width
        found_card['relative_h'] = 1.0 * circle_size / resized_height

    sys.stderr.write("%f elapsed before dumping\n" % (time.time() - start))
    sys.stdout.write(json.dumps(found_cards, indent=4, sort_keys=True))


if __name__ == '__main__':
    main()
