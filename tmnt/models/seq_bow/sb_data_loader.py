# coding: utf-8
"""
Copyright (c) 2019 The MITRE Corporation.
"""

import io
import itertools
import os
import logging
import json
import numpy as np
import re
import string
import gluonnlp as nlp
import mxnet as mx

from mxnet import gluon
from mxnet.gluon import nn
from mxnet import autograd as ag
from tmnt.bow_vae.bow_doc_loader import get_single_vec
from tmnt.seq_vae.tokenization import FullTokenizer, EncoderTransform, BasicTokenizer

from gluonnlp.data import BERTTokenizer, BERTSentenceTransform

__all__ = ['load_dataset_bert', 'load_dataset_basic', 'load_dataset_basic_seq_bow']

trans_table = str.maketrans(dict.fromkeys(string.punctuation))

def remove_punct_and_urls(txt):
    string = re.sub(r'https?:\/\/\S+\b|www\.(\w+\.)+\S*', '', txt) ## wipe out URLs
    return string.translate(trans_table)


def load_dataset_bert(json_file, voc_size, json_text_key="text", json_sp_key="sp_vec", max_len=64, ctx=mx.cpu()):
    indices = []
    values = []
    indptrs = [0]
    cumulative = 0
    total_num_words = 0
    ndocs = 0
    bert_model = 'bert_12_768_12'
    dname = 'book_corpus_wiki_en_uncased'
    bert_base, vocab = nlp.model.get_model(bert_model,  
                                             dataset_name=dname,
                                             pretrained=True, ctx=ctx, use_pooler=True,
                                             use_decoder=False, use_classifier=False)
    tokenizer = BERTTokenizer(vocab)
    transform = BERTSentenceTransform(tokenizer, max_len, pair=False) 
    x_ids = []
    x_val_lens = []
    x_segs = []
    with io.open(json_file, 'r', encoding='utf-8') as fp:
        for line in fp:
            if json_text_key:
                js = json.loads(line)
                line = js[json_text_key]
            if len(line.split(' ')) > 4:
                ids, lens, segs = transform((line,)) # create BERT-ready inputs
                x_ids.append(ids)
                x_val_lens.append(lens)
                x_segs.append(segs)
            ## Now, get the sparse vector
            ndocs += 1
            sp_vec_els = js[json_sp_key]
            n_pairs, inds, vs = get_single_vec(sp_vec_els)
            cumulative += n_pairs
            total_num_words += sum(vs)
            indptrs.append(cumulative)
            values.extend(vs)
            indices.extend(inds)
    csr_mat = mx.nd.sparse.csr_matrix((values, indices, indptrs), shape=(ndocs, voc_size))
    data_train = gluon.data.ArrayDataset(
        mx.nd.array(x_ids, dtype='int32'),
        mx.nd.array(x_val_lens, dtype='int32'),
        mx.nd.array(x_segs, dtype='int32'),
        csr_mat.tostype('default'))
    return data_train, bert_base, vocab, csr_mat


def load_dataset_basic_seq_bow(json_file, voc_size, vocab=None, json_text_key="text", json_sp_key="sp_vec",
                               max_len=64, max_vocab_size=20000, ctx=mx.cpu()):
    train_arr = []
    tokenizer = BasicTokenizer(do_lower_case=True)
    labels = []
    indices = []
    values = []
    indptrs = [0]
    cumulative = 0
    total_num_words = 0
    ndocs = 0
    if not vocab:        
        counter = None
        with io.open(json_file, 'r', encoding='utf-8') as fp:
            for line in fp:
                if json_text_key:
                    js = json.loads(line)
                    line = js[json_text_key]
                if len(line.split(' ')) > 4:
                    toks = tokenizer.tokenize(line)[:(max_len-2)]
                    counter = nlp.data.count_tokens(toks, counter = counter)
        vocab = nlp.Vocab(counter, max_size=max_vocab_size)
    pad_id = vocab[vocab.padding_token]
    logging.info("Vocabulary established from data file {} with ===> {} vocabulary items"
                 .format(json_file, len(vocab.idx_to_token)))
    dataset_list = []
    with io.open(json_file, 'r', encoding='utf-8') as fp:
        for line in fp:
            js = json.loads(line)
            text = js[json_text_key]
            if len(text.split(' ')) > 4:
                toks = tokenizer.tokenize(line)[:(max_len-2)]
                toks = ['<bos>'] + toks + ['<eos>']
                ids = []
                for t in toks:
                    try:
                        ids.append(vocab[t])
                    except:
                        ids.append(vocab['<unk>'])
                padded_ids = ids[:max_len] if len(ids) >= max_len else ids + [pad_id] * (max_len - len(ids))
                train_arr.append(padded_ids)                
                ## Now, get the sparse vector
                ndocs += 1
                sp_vec_els = js[json_sp_key]
                n_pairs, inds, vs = get_single_vec(sp_vec_els)
                cumulative += n_pairs
                total_num_words += sum(vs)
                indptrs.append(cumulative)
                values.extend(vs)
                indices.extend(inds)
    csr_mat = mx.nd.sparse.csr_matrix((values, indices, indptrs), shape=(ndocs, voc_size))
    dense_mat = csr_mat.tostype('default')
    np_tr_arr = mx.nd.array(train_arr, dtype='int32')
    logging.info("dense shape = {}, tr_array shape = {}, total num words = {}"
                 .format(dense_mat.shape, np_tr_arr.shape, total_num_words))
    ## include dense training array + the sparse csr matrix
    data_train = gluon.data.ArrayDataset(np_tr_arr, dense_mat)
    return data_train, vocab, csr_mat, total_num_words







