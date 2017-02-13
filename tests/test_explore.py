"""
Tests the hidden state correlation
"""

import pickle

# import tensorflow as tf
import numpy as np

from py.procedures import build_model, init_tf_environ, pour_data
from py.rnn.evaluator import StateRecorder
from py.db.language_model import query_evals, query_evaluation_records
from py.utils.io_utils import file_exists, lists2csv

# flags = tf.flags
# flags.DEFINE_integer('gpu_num', 0, "The number of the gpu to use, 0 to use no gpu.")
# FLAGS = flags.FLAGS

#
# def config_path():
#     return FLAGS.config_path


def fetch_states_of_eval(eval_id, state_name='state_c'):
    records = query_evaluation_records(eval_id)
    word_ids = [record['word_id'] for record in records]
    state_c = [record[state_name] for record in records]
    # state_h = [record['state_h'] for record in records]
    state_c_diff = [state_c[0]]
    for i in range(len(state_c)-1):
        state_c_diff.append(state_c[i+1] - state_c[i])
    return word_ids, state_c_diff


def fetch_states(data_name, model_name, state_name='state_c'):
    evals = query_evals(data_name, model_name)
    word_ids = []
    state_c_diff = []
    for eval in evals:
        eval_id = eval['_id']
        word_ids_, state_c_diff_ = fetch_states_of_eval(eval_id, state_name)
        word_ids += word_ids_
        state_c_diff += state_c_diff_
    return word_ids, state_c_diff


def sort_by_id(word_ids, states):
    max_id = max(word_ids)
    id_to_states = [None] * (max_id+1)
    for k, id_ in enumerate(word_ids):
        if id_to_states[id_] is None:
            id_to_states[id_] = []
        id_to_states[id_].append(states[k])
    return id_to_states


def compute_stats(states, sort_by_mean=True):
    layer_num = states[0].shape[0]
    states_layer_wise = []
    stds = []
    means = []
    errors_l = []
    errors_u = []
    indices = []
    idx = None
    for layer in range(layer_num):
        state_list = [state[layer] for state in states]
        states_mat = np.vstack(state_list)
        std = np.std(states_mat, axis=0)
        mean = np.mean(states_mat, axis=0)
        error_l = mean-np.min(states_mat, axis=0)
        error_u = np.max(states_mat, axis=0)-mean
        if sort_by_mean:
            idx = np.argsort(mean)
            mean = mean[idx]
            std = std[idx]
            error_u = error_u[idx]
            error_l = error_l[idx]
        indices.append(idx)
        stds.append(std)
        means.append(mean)
        errors_l.append(error_l)
        errors_u.append(error_u)
        states_layer_wise.append(states_mat)
    return stds, means, errors_l, errors_u, indices


def find_candidate(means, stds, k):
    means = np.vstack(means)
    stds = np.vstack(stds)
    candidate = []
    stds_ = []
    mean_ = []
    for i in range(means.shape[1]):
        idx = np.argpartition(-np.abs(means[:, i]), k)[:k]
        mean = means[idx, i]
        idx_ = np.argsort(-np.abs(mean))
        idx = idx[idx_]
        candidate.append(idx.tolist())
        mean_.append(means[idx, i].tolist())
        stds_.append(stds[idx, i].tolist())
    return candidate, mean_, stds_


def get_model_params(model_config):
    model, train_config = build_model(model_config, True)
    model.restore()
    embedding = model.embedding_weights
    return embedding


if __name__ == '__main__':

    data_name = 'ptb'
    model_name = 'LSTM-PTB'
    state_name = 'state_c'
    word_file = data_name + '-' + model_name + '-words.pkl'
    states_file = data_name + '-' + model_name + '-' + state_name + '.pkl'
    if file_exists(word_file) and file_exists(states_file):
        with open(word_file, 'rb') as f:
            words = pickle.loads(f.read())
        with open(states_file, 'rb') as f:
            state_diff = pickle.loads(f.read())
    else:
        words, state_diff = fetch_states(data_name, model_name, state_name)
        with open(word_file, 'wb') as f:
            pickle.dump(words, f)
        with open(states_file, 'wb') as f:
            pickle.dump(state_diff, f)

    # embedding = get_model_params('./config/rnn.yml')
    #
    id_to_state = sort_by_id(words, state_diff)
    id_freq = [len(states) if states is not None else 0 for states in id_to_state]
    # state_shape = state_diff[0].shape
    # layer_num = state_shape[0]
    # mean_n = [[] for i in range(layer_num)]
    # std_n = [[] for i in range(layer_num)]
    # for i, states in enumerate(id_to_state):
    #     if states is None:
    #         stds = np.zeros(state_shape, dtype=np.float32)
    #         means = np.zeros(state_shape, dtype=np.float32)
    #     else:
    #         stds, means, error_l, error_u, idx = compute_stats(states, False)
    #     for j, mean in enumerate(means):
    #         mean_n[j].append(mean)
    #     for j, std in enumerate(stds):
    #         std_n[j].append(std)
    #
    # for i in range(layer_num):
    #     cand, mean, std = find_candidate(mean_n[i][:1000], std_n[i][:1000], 20)
    #     lists2csv(cand, '-'.join(['cand', data_name, model_name, str(i), str(20)]) + '.csv')
    #     lists2csv(mean, '-'.join(['mean', data_name, model_name, str(i), str(20)]) + '.csv')
    #     lists2csv(std, '-'.join(['std', data_name, model_name, str(i), str(20)]) + '.csv')

    import matplotlib.pyplot as plt

    for i, states in enumerate(id_to_state):
        if i not in list(range(50, 60)):
            continue
        if states is None:
            continue
        stds, means, error_l, error_u, idx = compute_stats(states)

        fig, axes = plt.subplots(nrows=2, sharex=True, figsize=(9, 9))
        dim = slice(0, 600, 5)
        for j in range(2):
            axes[j].errorbar(range(len(means[j][dim])), means[j][dim], yerr=[error_l[j][dim], error_u[j][dim]])
            axes[j].errorbar(range(len(means[j][dim])), means[j][dim], yerr=stds[j][dim], capsize=5)

            axes[j].plot([0,dim.stop/dim.step], [0,0])
            axes[j].set_ylim([-2, 2])

        plt.show()

    # init_tf_environ(FLAGS.gpu_num)
    # datasets = get_datasets_by_name('ptb', ['test'])
    # test_data = datasets['test']

    # model, train_config = build_model('./config/lstm.yml', False)
    # model.add_evaluator(10, 1, 1)
    #
    # print('Preparing data')
    # producers = pour_data(train_config.dataset, ['test'], 10, 1)
    # inputs, targets, epoch_size = producers[0]
    # model.restore()
    #
    # model.run_with_context(model.evaluator.evaluate_and_record, inputs, targets,
    #                        StateRecorder(train_config.dataset, model.name), verbose=True)
