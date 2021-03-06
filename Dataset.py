import re
import zipfile
import pandas as pd
import sentencepiece as spm

from nltk.corpus import stopwords

stopwords_en = set(stopwords.words('english'))

import torch
from torch.utils.data import Dataset

with zipfile.ZipFile('data/open.zip', 'r') as zip_ref:
    zip_ref.extractall('data/')


def alpha_num(text):
    return re.sub(r'[^A-Za-z0-9 ]', '', text)


def remove_stopwords(text):
    final_text = []
    for i in text.split():
        if i.strip().lower() not in stopwords_en:
            final_text.append(i.strip())
    return " ".join(final_text)


class TextDataset(Dataset):
    def __init__(self, vocab_size, separation=True, train=True):
        self.train = train
        self.input_file = 'spm_input.txt'
        self.df = pd.read_csv('data/train.csv')
        self.df.text = self.df.text.str.lower().apply(alpha_num).apply(remove_stopwords)
        if separation:
            self.corpus = []
            self.authors = []
            for idx in self.df.index:
                texts = self.df.text[idx].split('. ')
                author = self.df.author[idx]
                for text in texts:
                    self.corpus.append(text)
                    self.authors.append(author)
        else:
            self.corpus = self.df.text.values.tolist()
            self.authors = self.df.author.values.tolist()
        with open(self.input_file, 'w', encoding='utf-8') as f:
            for sent in self.corpus:
                f.write('{}\n'.format(sent))
        spm.SentencePieceTrainer.train(
            f"--input={self.input_file} --model_prefix=train_vocab --vocab_size={vocab_size + 7}" +
            " --model_type=bpe" +
            " --max_sentence_length=20" +  # 문장 최대 길이
            " --pad_id=0 --pad_piece=[PAD]" +  # pad (0)
            " --unk_id=1 --unk_piece=[UNK]" +  # unknown (1)
            " --bos_id=2 --bos_piece=[BOS]" +  # begin of sequence (2)
            " --eos_id=3 --eos_piece=[EOS]" +  # end of sequence (3)
            " --user_defined_symbols=[SEP],[CLS],[MASK]")  # 사용자 정의 토큰
        self.vocab_file = "train_vocab.model"
        self.vocab = spm.SentencePieceProcessor()
        self.vocab.load(self.vocab_file)

        self.sentences = []
        self.labels = []
        for item, label in zip(self.corpus, self.authors):
            self.sentences.append(self.vocab.encode_as_ids(item))
            self.labels.append(label)
        if not train:
            self.df = pd.read_csv('data/test_x.csv', index_col='index')
            self.df.text = self.df.text.str.lower().apply(alpha_num).apply(remove_stopwords)
            if separation:
                self.corpus = []
                for idx in self.df.index:
                    texts = self.df.text[idx].split('. ')
                    for text in texts:
                        self.corpus.append(text)
            else:
                self.corpus = self.df.text.values.tolist()
            self.sentences = []
            for item in self.corpus:
                self.sentences.append(self.vocab.encode_as_ids(item))

    def __len__(self):
        if self.train:
            assert len(self.labels) == len(self.sentences)
            return len(self.sentences)
        else:
            return len(self.sentences)

    def __getitem__(self, idx):
        enc_inputs = torch.tensor(self.sentences[idx]).long()
        dec_inputs = torch.tensor([self.vocab.piece_to_id("[BOS]")])
        if self.train:
            label = torch.tensor(self.labels[idx])
            return enc_inputs, dec_inputs, label
        else:
            return enc_inputs, dec_inputs
