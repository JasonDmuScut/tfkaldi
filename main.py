# fix some pylint stuff
# fixes the np.random error
# pylint: disable=E1101
# fixes the unrecognized state_is_tuple
# pylint: disable=E1123
# fix the pylint import problem.
# pylint: disable=E0401

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

#to store the data and name it properly.
import pickle
import socket

import matplotlib.pyplot as plt
import tensorflow as tf
import numpy as np
from prepare.batch_dispenser import PhonemeTextDispenser
from prepare.batch_dispenser import UttTextDispenser
from prepare.feature_reader import FeatureReader
from neuralnetworks.nnet_graph import BlstmCtcModel
from neuralnetworks.nnet_trainer import Trainer

from IPython.core.debugger import Tracer; debug_here = Tracer()


def generate_dispenser(data_path, set_kind, label_no, batch_size, phonemes):
    ''' Instatiate a batch dispenser object using the data
        at the spcified path locations'''
    feature_path = data_path + set_kind + "/" + "feats.scp"
    cmvn_path = data_path + set_kind + "/" + "cmvn.scp"
    utt2spk_path = data_path + set_kind + "/" + "utt2spk"
    text_path = data_path + set_kind + "/" + "text"
    featureReader = FeatureReader(feature_path, cmvn_path, utt2spk_path)

    if phonemes is True:
        dispenser = PhonemeTextDispenser(featureReader, batch_size,
                                         text_path, label_no,
                                         max_time_steps)
    else:
        dispenser = UttTextDispenser(featureReader, batch_size,
                                     text_path, label_no,
                                     max_time_steps)
    return dispenser


###Learning Parameters
#LEARNING_RATE = 0.0008
LEARNING_RATE = 0.001
MOMENTUM = 0.9
#OMEGA = 0.1 #weight regularization term.
OMEGA = 0.000 #weight regularization term.
INPUT_NOISE_STD = 0.65
#LEARNING_RATE = 0.0001       #too low?
#MOMENTUM = 0.6              #play with this.
MAX_N_EPOCHS = 900


####Network Parameters
n_features = 40
#n_hidden = 164
#n_hidden = 180
n_hidden = 156



####Load timit data
timit = True
print('Loading data')
if timit:
    max_time_steps = 777
    TIMIT_LABELS = 39
    TIMIT_PATH = "/esat/spchtemp/scratch/moritz/dataSets/timit2/"
    TRAIN = "/train/40fbank"
    PHONEMES = True

    trainDispenser = generate_dispenser(TIMIT_PATH, TRAIN, TIMIT_LABELS,
                                        462, PHONEMES)

    VAL = "dev/40fbank"
    valDispenser = generate_dispenser(TIMIT_PATH, VAL, TIMIT_LABELS,
                                      400, PHONEMES)

    TEST = "test/40fbank"
    testDispenser = generate_dispenser(TIMIT_PATH, TEST, TIMIT_LABELS,
                                       192, PHONEMES)


    BATCH_COUNT = trainDispenser.get_batch_count()
    BATCH_COUNT_VAL = valDispenser.get_batch_count()
    BATCH_COUNT_TEST = testDispenser.get_batch_count()

    n_classes = TIMIT_LABELS + 1 #39 phonemes, plus the "blank" for CTC
else:
    max_time_steps = 2037
    AURORA_LABELS = 33
    AURORA_PATH = "/esat/spchtemp/scratch/moritz/dataSets/aurora/"
    TRAIN = "/train/40fbank"
    PHONEMES = False

    trainDispenser = generate_dispenser(AURORA_PATH, TRAIN, AURORA_LABELS,
                                        793, PHONEMES)
    TEST = "test/40fbank"
    valDispenser = generate_dispenser(AURORA_PATH, TEST, AURORA_LABELS,
                                      793, PHONEMES)

    testDispenser = generate_dispenser(AURORA_PATH, TEST, AURORA_LABELS,
                                       606, PHONEMES)

    testFeatureReader = valDispenser.split_reader(606)
    testDispenser.featureReader = testFeatureReader

    BATCH_COUNT = trainDispenser.get_batch_count()
    BATCH_COUNT_VAL = valDispenser.get_batch_count()
    BATCH_COUNT_TEST = testDispenser.get_batch_count()
    print(BATCH_COUNT, BATCH_COUNT_VAL, BATCH_COUNT_TEST)
    n_classes = AURORA_LABELS + 1 #33 letters, plus the "blank" for CTC


#set up network and trainer.
LEARNING_RATE_DECAY = 0

blstmCtcGraph = BlstmCtcModel('ctc_blstm', n_features, n_hidden, max_time_steps,
             n_classes, INPUT_NOISE_STD)
trainer = Trainer(blstmCtcGraph, LEARNING_RATE, OMEGA)

#debug_here()

def create_dict(batched_data_arg, noise_bool):
    '''Create an input dictonary to be fed into the tree.
    @return:
    The dicitonary containing the input numpy arrays,
    the three sparse vector data components and the
    sequence legths of each utterance.'''

    batch_inputs, batch_trgt_sparse, batch_seq_lengths = batched_data_arg
    batch_trgt_ixs, batch_trgt_vals, batch_trgt_shape = batch_trgt_sparse
    res_feed_dict = {blstmCtcGraph.input_x: batch_inputs,
                     trainer.target_ixs: batch_trgt_ixs,
                     trainer.target_vals: batch_trgt_vals,
                     trainer.target_shape: batch_trgt_shape,
                     blstmCtcGraph.seq_lengths: batch_seq_lengths,
                     blstmCtcGraph.noise_wanted: noise_bool}
    return res_feed_dict, batch_seq_lengths


####Run session
restarts = 0
epoch_loss_lst = []
epoch_error_lst = []
epoch_error_lst_val = []

with tf.Session(graph=trainer.model.tf_graph) as session:
    print('Initializing')
    tf.initialize_all_variables().run()

    #check untrained performance.
    input_batches = []
    for batch in range(0, BATCH_COUNT):
        input_batches.append(trainDispenser.get_batch())

    eval_loss, eval_error_rate = trainer.evaluate(input_batches, session)

    epoch_error_lst.append(eval_error_rate)
    epoch_loss_lst.append(eval_loss)
    print('Untrained error rate:', eval_error_rate)

    val_lst = [valDispenser.get_batch()]
    vl, ver = trainer.evaluate(val_lst, session)
    print("untrained validation loss: ", vl, " validation error rate", ver)
    epoch_error_lst_val.append(ver)

    continue_training = True
    while continue_training:
        epoch = len(epoch_error_lst_val)
        print('Epoch', epoch, '...')

        input_batches = []
        for batch in range(0, BATCH_COUNT):
            input_batches.append(trainDispenser.get_batch())

        trn_loss, trn_error_rate = trainer.update(input_batches, session)

        epoch_error_lst.append(trn_loss)
        epoch_loss_lst.append(trn_error_rate)
        print('error rate:', trn_error_rate)

        val_lst = [valDispenser.get_batch()]
        vl, ver = trainer.evaluate(val_lst, session)
        print("validation loss: ", vl, "error rate", ver)
        epoch_error_lst_val.append(ver)

        # if the training error is lower than the validation error for
        # interval iterations stop..
        interval = 50
        if epoch > interval:
            print("validation errors", epoch_error_lst_val[(epoch - interval):epoch])

            val_mean = np.mean(epoch_error_lst_val[(epoch - interval):epoch])
            train_mean = np.mean(epoch_error_lst[(epoch - interval):epoch])
            test_val = val_mean - train_mean - 0.02
            print('Overfit condition value:', test_val,
                  'remaining iterations: ', MAX_N_EPOCHS - epoch)
            if (test_val > 0) or (epoch > MAX_N_EPOCHS):
                continue_training = False
                print("stopping the training.")
        else:
            print("validation errors", epoch_error_lst_val)

    #run the network on the test data set.
    test_lst = [testDispenser.get_batch()]
    tl, ter = trainer.evaluate(test_lst, session)
    print("test loss: ", vl, "test error rate", ver)
    epoch_error_lst_val.append(ver)

filename = "saved/savedValsBLSTMAdam." + socket.gethostname() + ".pkl"
pickle.dump([epoch_loss_lst, epoch_error_lst,
             epoch_error_lst_val, ter, LEARNING_RATE,
             MOMENTUM, OMEGA, INPUT_NOISE_STD, n_hidden], open(filename, "wb"))
print("plot values saved at: " + filename)

plt.plot(np.array(epoch_loss_lst))
plt.plot(np.array(epoch_error_lst))
plt.plot(np.array(epoch_error_lst_val))
plt.show()
