"""
Use MongoDB to manage all the language modeling datasets
"""

import os
import json
import itertools
import random
import yaml

from rnnvis.utils.io_utils import dict2json, get_path, path_exists
from rnnvis.datasets.data_utils import split
from rnnvis.datasets.text_processor import SSTProcessor, tokenize, tokens2vocab
from rnnvis.datasets.sst_helper import download_sst
from rnnvis.datasets import imdb
from rnnvis.db.db_helper import insert_one_if_not_exists, replace_one_if_exists, \
    store_dataset_by_default, dataset_inserted

def store_sst(data_path, name, split_scheme, upsert=False):
    """
    Process and store the ptb datasets to db
    :param data_path:
    :param name:
    :param upsert:
    :return:
    """
    if not path_exists(data_path):
        download_sst(os.path.abspath(os.path.join(data_path, '../')))
    if upsert:
        insertion = replace_one_if_exists
    else:
        insertion = insert_one_if_not_exists
    phrase_path = os.path.join(data_path, "dictionary.txt")
    sentence_path = os.path.join(data_path, "datasetSentences.txt")
    label_path = os.path.join(data_path, "sentiment_labels.txt")
    sentence_split_path = os.path.join(data_path, "datasetSplit.txt")
    processor = SSTProcessor(sentence_path, phrase_path, label_path, sentence_split_path)

    split_data = split(list(zip(processor.ids, processor.labels, range(1, len(processor.labels)+1))),
                       split_scheme.values(), shuffle=True)
    split_data = dict(zip(split_scheme.keys(), split_data))
    sentence_data_ids = processor.split_sentence_ids

    word_to_id_json = dict2json(processor.word_to_id)
    insertion('word_to_id', {'name': name}, {'name': name, 'data': word_to_id_json})
    insertion('id_to_word', {'name': name}, {'name': name, 'data': processor.id_to_word})
    for i, set_name in enumerate(['train', 'valid', 'test']):
        data, ids = zip(*(sentence_data_ids[i]))
        insertion('sentences', {'name': name, 'set': set_name},
                  {'name': name, 'set': set_name, 'data': data, 'ids': ids})

    if 'train' not in split_data:
        print('WARN: there is no train data in the split data!')
    data_dict = {}
    for set_name in ['train', 'valid', 'test']:
        if set_name in split_data:
            data, label, ids = zip(*split_data[set_name])
            # convert label to 1,2,3,4,5
            label = [float(i) for i in label]
            label = [(0 if i <= 0.2 else 1 if i <= 0.4 else 2 if i <= 0.6 else 3 if i <= 0.8 else 4) for i in label]
            data_dict[set_name] = {'data': data, 'label': label, 'ids': ids}
    store_dataset_by_default(name, data_dict, upsert)


def store_imdb(data_path, name, n_words=100000, upsert=False):
    if upsert:
        insertion = replace_one_if_exists
    else:
        insertion = insert_one_if_not_exists
    word_to_id, id_to_word = imdb.load_dict(os.path.join(data_path, 'imdb.dict.pkl.gz'), n_words)
    data_label = imdb.load_data(os.path.join(data_path, 'imdb.pkl'), n_words)
    word_to_id_json = dict2json(word_to_id)
    insertion('word_to_id', {'name': name}, {'name': name, 'data': word_to_id_json})
    insertion('id_to_word', {'name': name}, {'name': name, 'data': id_to_word})

    data_dict = {}
    for i, set_name in enumerate(['train', 'valid', 'test']):
        data, label = data_label[i]
        ids = list(range(len(data)))
        # insertion('sentences', {'name': name, 'set': set_name},
        #           {'name': name, 'set': set_name, 'data': data, 'label': label, 'ids': ids})
        data_dict[set_name] = {'data': data, 'label': label, 'ids': ids}
    store_dataset_by_default(name, data_dict, upsert)


def store_yelp(data_path, name, n_words=10000, upsert=False):
    if upsert:
        insertion = replace_one_if_exists
    else:
        insertion = insert_one_if_not_exists
    with open(os.path.join(data_path, 'review_label.json'), 'r') as file:
        data = json.load(file)
    all_words = []
    # reviews = []
    # stars = []
    for item in data:
        tokenized_review = list(itertools.chain.from_iterable(tokenize(item['review'], remove_punct=True)[0]))
        item['review'] = (tokenized_review)
        # stars.append(item['label'])
        all_words.extend(tokenized_review)
    word_to_id, counter, words = tokens2vocab(all_words)
    n_words -= 1
    word_to_id = {k: v+1 for k, v in word_to_id.items() if v < n_words}
    word_to_id['<unk>'] = 0

    id_to_word = [None] * len(word_to_id)
    for word, id_ in word_to_id.items():
        id_to_word[id_] = word

    if name == 'yelp-2':
        positives = []
        negatives = []
        for item in data:
            if item['label'] < 3:
                item['label'] = 0
                negatives.append(item)
            elif item['label'] > 3:
                item['label'] = 1
                positives.append(item)
        print("{0} positive reviews, {1} negative reviews".format(len(positives), len(negatives)))
        if len(positives) < len(negatives):
            negatives = random.sample(negatives, len(positives))
        elif len(positives) > len(negatives):
            positives = random.sample(positives, len(negatives))
        data = positives + negatives

    reviews = [[word_to_id.get(t,0) for t in item['review']] for item in data]
    stars = [item['label'] for item in data]
    training_data, validate_data, test_data = split(list(zip(reviews, stars)), fractions=[0.8, 0.1, 0.1], shuffle=True)

    word_to_id_json = dict2json(word_to_id)
    insertion('word_to_id', {'name': name}, {'name': name, 'data': word_to_id_json})
    insertion('id_to_word', {'name': name}, {'name': name, 'data': id_to_word})

    data_names = ['train', 'valid', 'test']
    data_dict = {}
    for i, data_set in enumerate([training_data, validate_data, test_data]):
        data_set = zip(*sorted(data_set, key=lambda x: len(x[0])))
        data, label = data_set
        ids = list(range(len(data)))
        data_dict[data_names[i]] = {'data': data, 'label': label, 'ids': ids}
        #insertion('sentences', {'name': name, 'set': data_names[i]},
        #          {'name': name, 'set': data_names[i], 'data': data, 'label': label, 'ids': ids})
    store_dataset_by_default(name, data_dict, upsert)


def get_dataset_path(name):
    return os.path.join('data', 'sentiment_prediction', name)


def seed_db(force=False):
    """
    Use the `config/datasets/lm.yml` to generate example datasets and store them into db.
    :return: None
    """
    config_dir = get_path('config/db', 'sp.yml')
    with open(config_dir, 'r') as f:
        config = yaml.safe_load(f)['datasets']
    for seed in config:
        print('seeding {:s} data'.format(seed['name']))
        data_dir = get_path('data', seed['dir'])
        seed['scheme'].update({'upsert': force})
        if seed['type'] == 'sst':
            store_sst(data_dir, seed['name'], **seed['scheme'])
        elif seed['type'] == 'imdb':
            store_imdb(data_dir, seed['name'], **seed['scheme'])
        elif seed['type'] == 'yelp':
            store_yelp(data_dir, seed['name'], **seed['scheme'])
        else:
            print('not able to seed datasets with type: {:s}'.format(seed['type']))
            continue
        dataset_inserted(seed['name'], 'sp')


if __name__ == '__main__':
    # store_ptb(get_path('cached_data/simple-examples/data'))
    # store_plain_text(get_path('cached_data/tinyshakespeare.txt'), 'shakespeare',
    # {'train': 0.9, 'valid': 0.05, 'test': 0.05})
    seed_db(force=True)
    # data = get_datasets_by_name('sst', ['train', 'valid', 'word_to_id'])
    # train_data = data['train']
    # test_data = data['test']
