# Copyright 2018 luozhouyang
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

import tensorflow as tf

from naivenmt.encoders import BasicEncoder
from naivenmt.tests import common_test_utils as common_utils

NUM_LAYERS_2 = 2
NUM_LAYERS_4 = 4


class BasicBiEncodersTest(tf.test.TestCase):

  def runGRUEncoder(self, encoder, num_layers):
    """Test GRU cell outputs and states. time_major=True

    Args:
      encoder: Instance of BasicEncoder, unit type is 'gru'.
      num_layers: A integer, number of layers.
    """
    inputs_ph = tf.placeholder(
      dtype=tf.float32,
      shape=(None, common_utils.TIME_STEPS, common_utils.DEPTH))
    inputs_length_ph = tf.placeholder(dtype=tf.int32, shape=(None))

    # states is a tuple of (states_fw, states_bw)
    # states_fw is a tuple of (state) of length num_layers
    outputs, states = encoder.encode(
      mode=tf.estimator.ModeKeys.TRAIN,
      sequence_inputs=inputs_ph,
      sequence_length=inputs_length_ph)

    self.assertEqual(num_layers, len(states))

    states = tf.convert_to_tensor(states)

    inputs, inputs_length = common_utils.get_encoder_test_inputs()
    with self.test_session() as sess:
      sess.run(tf.global_variables_initializer())
      outputs, states = sess.run(
        [outputs, states],
        feed_dict={
          inputs_ph: inputs,
          inputs_length_ph: inputs_length
        })

      # outputs shape: (time_steps, batch_size, depth*2)
      self.assertAllEqual(
        [common_utils.TIME_STEPS, common_utils.BATCH_SIZE,
         common_utils.DEPTH * 2],
        outputs.shape)

      self.assertAllEqual(
        [num_layers, common_utils.BATCH_SIZE, common_utils.DEPTH],
        states.shape)

  def runLSTMEncoder(self, encoder, num_layers):
    """Test LSTM, LayerNormLSTM and NAS cell outputs and states. time_major=True

    Args:
      encoder: Instance of BasicEncoder,
        unit type is one of 'lstm', 'layer_norm_lstm', 'nas'.
      num_layers: A integer, number of layers.
    """
    inputs_ph = tf.placeholder(
      dtype=tf.float32,
      shape=(None, common_utils.TIME_STEPS, common_utils.DEPTH))
    inputs_length_ph = tf.placeholder(dtype=tf.int32, shape=(None))

    # states is a tuple of (states_fw/states_bw) of length num_layers
    outputs, states = encoder.encode(
      mode=tf.estimator.ModeKeys.TRAIN,
      sequence_inputs=inputs_ph,
      sequence_length=inputs_length_ph)

    self.assertEqual(num_layers, len(states))

    states = tf.convert_to_tensor(states)

    inputs, inputs_length = common_utils.get_encoder_test_inputs()
    with self.test_session() as sess:
      sess.run(tf.global_variables_initializer())
      outputs, states = sess.run(
        [outputs, states],
        feed_dict={
          inputs_ph: inputs,
          inputs_length_ph: inputs_length
        })
      # outputs shape: (time_steps, batch_size, depth*2)
      self.assertAllEqual(
        [common_utils.TIME_STEPS, common_utils.BATCH_SIZE,
         common_utils.DEPTH * 2],
        outputs.shape)
      # states shape: (num_layers, 2, batch_size, depth), 2 means c and h.
      self.assertAllEqual(
        [num_layers, 2, common_utils.BATCH_SIZE, common_utils.DEPTH],
        states.shape)

  def testBasicLSTMEncoder(self):
    for num_layers in [NUM_LAYERS_2, NUM_LAYERS_4]:
      configs = {
        "unit_type": "lstm",
        "encoder_type": "bi",
        "num_encoder_layers": num_layers,
        "forget_bias": 1.0,
        "time_major": True
      }
      encoder = BasicEncoder(params=common_utils.get_params(configs))
      self.runLSTMEncoder(encoder, num_layers)

  def testBasicLayerNormLSTMEncoder(self):
    for num_layers in [NUM_LAYERS_2, NUM_LAYERS_4]:
      configs = {
        "unit_type": "layer_norm_lstm",
        "encoder_type": "bi",
        "num_encoder_layers": num_layers,
        "forget_bias": 1.0,
        "time_major": True
      }
      encoder = BasicEncoder(params=common_utils.get_params(configs))
      self.runLSTMEncoder(encoder, num_layers)

  def testBasicNASEncoder(self):
    for num_layers in [NUM_LAYERS_2, NUM_LAYERS_4]:
      configs = {
        "unit_type": "nas",
        "encoder_type": "bi",
        "num_encoder_layers": num_layers,
        "forget_bias": 1.0,
        "time_major": True
      }
      encoder = BasicEncoder(params=common_utils.get_params(configs))
      self.runLSTMEncoder(encoder, num_layers)

  def testBasicGRUEncoder(self):
    for num_layers in [NUM_LAYERS_2, NUM_LAYERS_4]:
      configs = {
        "unit_type": "gru",
        "encoder_type": "bi",
        "num_encoder_layers": num_layers,
        "time_major": True
      }
      encoder = BasicEncoder(params=common_utils.get_params(configs))
      self.runGRUEncoder(encoder, num_layers)


if __name__ == "__main__":
  tf.test.main()
