Quickstart Guide
================


1. Building the Test Model
++++++++++++++++++++++++++

Training a topic model requires both a training file containing sparse vector representations of documents
along with a test/validation file in the same format. In addition, a vocabulary file is needed to
map token indices back to their string representations.  See preparing data (below) for how to
process a corpus of text data into this sparse vector format.

Once the prepared files are in place, training a model invovles invoking the ``train_model.py`` script
found in the ``bin/`` directory.  Using the example data provided (20 news corpus), 
a model is built on the data as follows::

  mkdir _experiments

  python bin/train_model.py --tr_vec_file ./data/train.vec \
  --val_vec_file ./data/test.vec --vocab_file ./data/train.vocab \
  --config ./examples/train_model/model.config \
  --save_dir ./_exps/ --log_level info

In general, TMNT assumes a test/validation corpus is available to determine the validation perplexity
and coherence, specified with the ``val_vec_file`` option.  If a validation file is not available/needed
it may be ommitted in which case no evaluation is performed.  See the :ref:`training-label`.


2. Preparing text data
++++++++++++++++++++++

The sparse vector representation for a corpus can be obtained from two different input formats:
1) json objects with one document per json object or 2) plain text documents (one document per file) 

Using the JSON input format, the value of the key ``text`` will be used as the document string.
All other fields are ignored. So, for example::


  {"id": "3664", "text": "This is the text of one of the documents in the corpus."}
  {"id": "3665", "text": "This is the text of another document in the corpus."}
  ...

Two directories of such files should be provided, one for training and one for test.  Assuming the files end with ``.json`` extensions, the
following example invocation would prepare the data for the training and test sets, creating vector representations with a vocabulary
size of 2000.  Note that this script uses the built in pre-processing which tokenizes, downcases and removes common English stopwords.
An example invocation::

  python bin/prepare_corpus.py --vocab_size 2000 --file_pat '*.json' --tr_input_dir ./train-json-files/ \
  --val_input_dir ./val-json-files/ --tr_vec_file ./train.2k.vec --vocab_file ./2k.vocab  --val_vec_file ./val.2k.vec 


The plain text input format assumes directories for training, validation and test sets, where each file is a separate plain text document. This should be
invoked by adding the ``--txt_mode`` option::


  python bin/prepare_corpus.py --vocab_size 2000 --file_pat '*.txt' --tr_input_dir ./train-txt-files/ \
  --val_input_dir ./val-txt-files/ --tr_vec_file ./train.2k.vec --vocab_file ./2k.vocab  \
  --val_vec_file ./val.2k.vec --txt_mode
   

TMNT does its own rudimentary pre-processing of the text and includes a built-in stop-word list for English
to remove certain common terms that tend to act as distractors for the purposes of generating coherent topics.
Custom stop-word lists can also be provided. 

