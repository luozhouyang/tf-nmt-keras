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

import abc
import codecs

import numpy as np
import tensorflow as tf
from tensorflow.python.ops import lookup_ops

VOCAB_SIZE_THRESHOLD = 50000


class EmbeddingInterface(abc.ABC):

  @abc.abstractmethod
  def encoder_embedding(self):
    """Create embedding for encoder."""
    raise NotImplementedError()

  @abc.abstractmethod
  def decoder_embedding(self):
    """Create embedding for decoder."""
    raise NotImplementedError()

  @abc.abstractmethod
  def encoder_embedding_input(self, inputs):
    """Create encoder embedding input.

    Args:
      inputs: A tf.string tensor

    Returns:
      embedding presentation of inputs
    """
    raise NotImplementedError()

  @abc.abstractmethod
  def decoder_embedding_input(self, inputs):
    """Create decoder embedding input.

    Args:
      inputs: A tf.string tensor

    Returns:
      embedding presentation of inputs
    """
    raise NotImplementedError()


class Embedding(EmbeddingInterface):

  def __init__(self,
               src_vocab_size,
               tgt_vocab_size,
               src_embedding_size,
               tgt_embedding_size,
               src_vocab_file,
               tgt_vocab_file,
               src_embedding_file=None,
               tgt_embedding_file=None,
               share_vocab=False,
               num_partitions=0,
               unk='<unk>',
               unk_id=0,
               dtype=tf.float32,
               scope="embedding"):
    self.share_vocab = share_vocab
    self.src_vocab_file = src_vocab_file
    self.tgt_vocab_file = tgt_vocab_file
    self.src_vocab_size = src_vocab_size
    self.tgt_vocab_size = tgt_vocab_size
    self.src_embedding_size = src_embedding_size
    self.tgt_embedding_size = tgt_embedding_size
    self.src_embedding_file = src_embedding_file
    self.tgt_embedding_file = tgt_embedding_file
    self.num_partitions = num_partitions
    self.dtype = dtype or tf.float32
    self.scope = scope or "embedding"
    self._encoder_embedding = None
    self._decoder_embedding = None

    self.unk = unk
    self.unk_id = unk_id

    self.src_str2idx_table = lookup_ops.index_table_from_file(
      self.src_vocab_file, default_value=self.unk_id)
    self.src_idx2str_table = lookup_ops.index_to_string_table_from_file(
      self.src_vocab_file, default_value=self.unk)
    self.tgt_str2idx_table = lookup_ops.index_table_from_file(
      self.tgt_vocab_file, default_value=self.unk_id)
    self.tgt_idx2str_table = lookup_ops.index_to_string_table_from_file(
      self.tgt_vocab_file, default_value=self.unk)
    self._embedding()

  def _embedding(self):
    if self.num_partitions <= 1:
      partitioner = None
    else:
      partitioner = tf.fixed_size_partitioner(num_shards=self.num_partitions)

    if (self.src_embedding_file or self.tgt_embedding_file) and partitioner:
      raise ValueError(
        "Can't set num_partitions > 1 when using pretrained embedding")

    with tf.variable_scope(self.scope, dtype=self.dtype,
                           partitioner=partitioner,
                           reuse=tf.AUTO_REUSE) as scope:
      self._encoder_embedding = self._create_or_load_embeddings(
        name="encoder_embedding",
        vocab_file=self.src_vocab_file,
        embedding_file=self.src_embedding_file,
        vocab_size=self.src_vocab_size,
        embedding_size=self.src_embedding_size,
        dtype=self.dtype)
      if self.share_vocab:
        if self.src_vocab_size != self.tgt_vocab_size:
          raise ValueError("Share embedding but different src/tgt vocab size.")
        self._decoder_embedding = self._encoder_embedding
      else:
        self._decoder_embedding = self._create_or_load_embeddings(
          name="decoder_embedding",
          vocab_file=self.tgt_vocab_file,
          vocab_size=self.tgt_vocab_size,
          embedding_file=self.tgt_embedding_file,
          embedding_size=self.tgt_embedding_size,
          dtype=self.dtype)
      return self._encoder_embedding, self._decoder_embedding

  def _create_or_load_embeddings(self,
                                 name,
                                 vocab_file,
                                 embedding_file,
                                 vocab_size,
                                 embedding_size,
                                 dtype):
    if vocab_file and embedding_file:
      embedding = self._create_pretrained_embedding(vocab_file, embedding_file)
    else:
      with tf.device(self._create_embedding_device(vocab_size)):
        embedding = tf.get_variable(
          name=name,
          shape=[vocab_size, embedding_size],
          dtype=dtype)
    return embedding

  def _create_pretrained_embedding(self,
                                   vocab_file,
                                   embedding_file,
                                   num_trainable_tokens=3,
                                   dtype=tf.float32,
                                   scope="pretrained_embedding"):
    vocab, _ = self._load_vocab(vocab_file)
    trainable_tokens = vocab[:num_trainable_tokens]
    embedding_dict, embedding_size = self._load_embedding_txt(embedding_file)
    for token in trainable_tokens:
      if token not in embedding_dict:
        embedding_dict[token] = [0.0] * embedding_size
    embedding_matrix = np.array(
      [embedding_dict[token] for token in vocab], dtype=dtype.as_numpy_dtype)
    embedding_matrix = tf.constant(embedding_matrix)
    embedding_matrix_const = tf.slice(
      embedding_matrix, [num_trainable_tokens, 0], [-1, -1])
    with tf.variable_scope(scope, dtype=dtype, reuse=tf.AUTO_REUSE):
      embedding_matrix_variable = tf.get_variable(
        "embedding_matrix_variable",
        [num_trainable_tokens, embedding_size])
    return tf.concat([embedding_matrix_variable, embedding_matrix_const], 0)

  @staticmethod
  def _load_vocab(vocab_file):
    vocab = []
    with codecs.getreader("utf-8")(tf.gfile.GFile(vocab_file, "rb")) as f:
      vocab_size = 0
      for word in f:
        vocab_size += 1
        vocab.append(word.strip())
    return vocab, vocab_size

  @staticmethod
  def _load_embedding_txt(embedding_file):
    embedding_dict = dict()
    embedding_size = None
    with codecs.getreader("utf-8")(tf.gfile.GFile(embedding_file, "rb")) as f:
      for line in f:
        tokens = line.strip().split(" ")
        word = tokens[0]
        vec = list(map(float, tokens[1:]))
        embedding_dict[word] = vec
        if embedding_size:
          assert embedding_size == len(vec), "All embedding size should be same"
        else:
          embedding_size = len(vec)
    return embedding_dict, embedding_size

  @staticmethod
  def _create_embedding_device(vocab_size):
    if vocab_size > VOCAB_SIZE_THRESHOLD:
      return "/cpu:0"
    else:
      return "/gpu:0"

  @property
  def encoder_embedding(self):
    return self._encoder_embedding

  @property
  def decoder_embedding(self):
    return self._decoder_embedding

  def encoder_embedding_input(self, inputs):
    inputs_ids = self.src_str2idx_table.lookup(inputs)
    return tf.nn.embedding_lookup(self.encoder_embedding, inputs_ids)

  def decoder_embedding_input(self, inputs):
    inputs_ids = self.tgt_str2idx_table.lookup(inputs)
    return tf.nn.embedding_lookup(self.decoder_embedding, inputs_ids)
