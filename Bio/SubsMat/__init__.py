__all__ = ["SubsMat","FreqTable","MatrixInfo"]

import sys
import copy
import math
import UserDict
# BioPython imports
from Bio import Alphabet
from Bio.SubsMat import FreqTable

log = math.log
# Matrix types
NOTYPE = 0
ACCREP = 1
OBSFREQ = 2
SUBS = 3
EXPFREQ = 4
LO = 5
class BadMatrix(Exception):
    """Exception raised when verifying a matrix"""
    def __str__(self):
        return "Bad Matrix"
BadMatrixError = BadMatrix()

#
# Substitution matrix routines
# Copyright 2000 Iddo Friedberg idoerg@cc.huji.ac.il
# All rights reserved. Biopython license applies (http://biopython.org)
# 
# General:
# -------
# You should have python 1.5.2 (need to test w/ 2.0!) 
# http://www.python.org
# You should have biopython (http://biopython.org) installed.
# 
# This module provides a class and a few routines for generating
# substitution matrices, similar ot BLOSUM or PAM matrices, but based on
# user-provided data.
# The class used for these matrices is SeqMatC
# 
# Matrices are implemented as a user dictionary. Each index contains a
# 2-tuple, which are the two residue/nucleotide types replaced. The value
# differs according to the matrix's purpose: e.g in a log-odds frequency
# matrix, the value would be log(Pij/(Pi*Pj)) where:
# Pij: frequency of substitution of letter (residue/nucletide) i by j 
# Pi, Pj: expected frequencies of i and j, respectively.
# 
# Usage:
# -----
# The following section is layed out in the order by which most people wish
# to generate a log-odds matrix. Of course, interim matrices can be
# generated and investigated. Most people just want a log-odds matrix,
# that's all.
# 
# Generating an Accepted Replacement Matrix:
# -----------------------------------------
#  Initially, you should generate an accepted replacement matrix
#  (ARM) from your data. The values in ARM are the _counted_ number of
#  replacements according to your data. The data could be a set of pairs
#  or multiple alignments. So for instance if Alanine was replaced by
#  Cysteine 10 times, and Cysteine by Alanine 12 times, the corresponding
#  ARM entries would be:
#  ['A','C']: 10, ['C','A'] 12
#  as order doesn't matter, user can already provide only one entry:
#  ['A','C']: 22 
#  A SeqMat instance may be initialized with either a full (first
#  method of counting: 10, 12) or half (the latter method, 22) matrices. A
#  Full protein alphabet matrix would be of the size 20x20 = 400. A Half
#  matrix of that alphabet would be 20x20/2 + 20/2 = 210. That is because
#  same-letter entries don't change. (The matrix diagonal). Given an
#  alphabet size of N:
#  Full matrix size:N*N
#  Half matrix size: N(N+1)/2
#  
#  If you provide a full matrix, the constructore will create a half-matrix
#  automatically.
#  If you provide a half-matrix, make sure
#  of a (low, high) sorted order in the keys: there should only be 
#  a ('A','C') not a ('C','A').
#
# Internal functions:
# 
# Generating the observed frequency matrix (OFM):
# ----------------------------------------------
#  Use: OFM = _build_obs_freq_mat(ARM)
#  The OFM is generated from the ARM, only instead of replacement counts, it
#  contains replacement frequencies.
# Generating an expected frequency matrix (EFM):
# ---------------------------------------------
#  Use: EFM = _build_exp_freq_mat(OFM,exp_freq_table)
#  exp_freq_table: should be a freqTableC instantiation. See freqTable.py for
#  detailed information. Briefly, the expected frequency table has the
#  frequencies of appearance for each member of the alphabet
# Generating a substitution frequency matrix (SFM):
# ------------------------------------------------
#  Use: SFM = _build_subs_mat(OFM,EFM)
#  Accepts an OFM, EFM. Provides the division product of the corresponding
#  values. 
# Generating a log-odds matrix (LOM):
# ----------------------------------
#  Use: LOM=_build_log_odds_mat(SFM[,logbase=10,factor=10.0,roundit=1])
#  Accepts an SFM. logbase: base of the logarithm used to generate the
#  log-odds values. factor: factor used to multiply the log-odds values.
#  roundit: default - true. Whether to round the values.
#  Each entry is generated by log(LOM[key])*factor
#  And rounded if required.
#
# External:
# ---------
# In most cases, users will want to generate a log-odds matrix only, without
# explicitly calling the OFM --> EFM --> SFM stages. The function
# build_log_odds_matrix does that. User provides an ARM and an expected
# frequency table. The function returns the log-odds matrix
#
class SeqMat(UserDict.UserDict):
    """A Generic sequence matrix class
    The key is a 2-tuple containing the letter indices of the matrix. Those
    should be sorted in the tuple (low, high). Because each matrix is dealt
    with as a half-matrix."""

    def _alphabet_from_matrix(self):
        ab_dict = {}
        s = ''
        for i in self.keys():
            ab_dict[i[0]] = 1
            ab_dict[i[1]] = 1
        letters_list = ab_dict.keys()
        letters_list.sort()
        for i in letters_list:
            s = s + i
        self.alphabet.letters = s

    def __init__(self,data=None, alphabet=None,
                 mat_type=NOTYPE,mat_name='',build_later=0):
        # User may supply:
        # data: matrix itself
        # mat_type: its type. See below
        # mat_name: its name. See below.
        # alphabet: an instance of Bio.Alphabet, or a subclass. If not
        # supplied, constructor builds its own from that matrix."""
        # build_later: skip the matrix size assertion. User will build the
        # matrix after creating the instance. Constructor builds a half matrix
        # filled with zeroes.

        assert type(mat_type) == type(1)
        assert type(mat_name) == type('')

        # "data" may be:
        # 1) None --> then self.data is an empty dictionary
        # 2) type({}) --> then self.data takes the items in data
        # 3) An instance of SeqMat
        # This whole creation-during-execution is done to avoid changing
        # default values, the way Python does because default values are
        # created when the function is defined, not when it is created.
        assert (type(data) == type({}) or isinstance(data,UserDict.UserDict) or
                  data == None)
        if data == None:
            data = {}
        if type(data) == type({}):
            self.data = copy.copy(data)
        else:
            self.data = copy.copy(data.data)
        if alphabet == None:
            alphabet = Alphabet.Alphabet()
        assert Alphabet.generic_alphabet.contains(alphabet)
        self.alphabet = alphabet

        # If passed alphabet is empty, use the letters in the matrix itself
        if not self.alphabet.letters:
            self._alphabet_from_matrix()
        # Assert matrix size: half or full
        if not build_later:
            N = len(self.alphabet.letters)
            assert len(self) == N**2 or len(self) == N*(N+1)/2
        self.ab_list = list(self.alphabet.letters)
        self.ab_list.sort()
        # type can be: ACCREP, OBSFREQ, SUBS, EXPFREQ, LO
        self.mat_type = mat_type
        # Names: a string like "BLOSUM62" or "PAM250"
        self.mat_name = mat_name
        if build_later:
            self._init_zero()
        else:
            self._full_to_half()
        self.sum_letters = {}

    def _full_to_half(self):
        """
        Convert a full-matrix to a half-matrix
        """
        # For instance: two entries ('A','C'):13 and ('C','A'):20 will be summed
        # into ('A','C'): 33 and the index ('C','A') will be deleted
        # alphabet.letters:('A','A') and ('C','C') will remain the same.

        N = len(self.alphabet.letters)
        # Do nothing if this is already a half-matrix
        if len(self) == N*(N+1)/2:
            return
        for i in self.ab_list:
            for j in self.ab_list[:self.ab_list.index(i)+1]:
                if i <> j:
                    self[j,i] = self[j,i] + self[i,j]
                    del self[i,j]

    def _init_zero(self):
        for i in self.ab_list:
            for j in self.ab_list[:self.ab_list.index(i)+1]:
                self[j,i] = 0.

    def entropy(self,obs_freq_mat):
        """if this matrix is a log-odds matrix, return its entropy
        Needs the observed frequency matrix for that"""
        ent = 0.
        if self.mat_type == LO:
            for i in self.keys():
                ent = ent+obs_freq_mat[i]*self[i]/log(2)
        elif self.mat_type == SUBS:
            for i in self.keys():
                ent = ent + obs_freq_mat[i]*log(self[i])/log(2)
        else:
            raise TypeError,"entropy: substitution or log-odds matrices only"
        return ent
    #
    def letter_sum(self,letter):
        assert letter in self.alphabet.letters
        sum = 0.
        for i in self.keys():
            if letter in i:
                if i[0] == i[1]:
                    sum += self[i]
                else:
                    sum += (self[i] / 2.)
        return sum

    def all_letters_sum(self):
        for letter in self.alphabet.letters:
            self.sum_letters[letter] = self.letter_sum(letter)
            
    def print_mat(self,f=sys.stdout,format="%4d",bottomformat="%4s",
                  alphabet=None): 
        """Print a nice half-matrix. f=sys.stdout to see on the screen
        User may pass own alphabet, which should contain all letters in the
        alphabet of the matrix, but may be in a different order. This
        order will be the order of the letters on the axes"""

        if not alphabet:
            alphabet = self.ab_list
        bottomline = ''
        for i in alphabet:
            bottomline = bottomline + bottomformat % i
        bottomline = bottomline + '\n'
        for i in alphabet:
            outline = i
            for j in alphabet[:alphabet.index(i)+1]:
                try:
                    val = self[j,i]
                except KeyError:
                    val = self[i,j]
                cur_str = format % val
                
                outline = outline+cur_str
            outline = outline+'\n'
            f.write(outline)
        f.write(bottomline)

def _build_obs_freq_mat(acc_rep_mat):
    """
    build_obs_freq_mat(acc_rep_mat):
   Build the observed frequency matrix, from an accepted replacements matrix
   The accRep matrix should be generated by the user.
    """
    sum = 0.
    for i in acc_rep_mat.values():
        sum += i
    obs_freq_mat = SeqMat(alphabet=acc_rep_mat.alphabet,build_later=1)
    for i in acc_rep_mat.keys():
        obs_freq_mat[i] = acc_rep_mat[i]/sum
    obs_freq_mat.mat_type = OBSFREQ
    return obs_freq_mat

def _exp_freq_table_from_obs_freq(obs_freq_mat):
    exp_freq_table = {}
    for i in obs_freq_mat.alphabet.letters:
        exp_freq_table[i] = 0.
    for i in obs_freq_mat.keys():
        if i[0] == i[1]:
            exp_freq_table[i[0]] += obs_freq_mat[i]
        else:
            exp_freq_table[i[0]] += obs_freq_mat[i] / 2.
            exp_freq_table[i[1]] += obs_freq_mat[i] / 2.
    return FreqTable.FreqTable(exp_freq_table,FreqTable.FREQ)

def _build_exp_freq_mat(exp_freq_table):
    """Build an expected frequency matrix
    exp_freq_table: should be a FreqTable instantiation
    """
    exp_freq_mat = SeqMat(alphabet=exp_freq_table.alphabet,build_later=1)
    for i in exp_freq_mat.keys():
        if i[0] == i[1]:
            exp_freq_mat[i] = exp_freq_table[i[0]]**2
        else:
            exp_freq_mat[i] = 2.0*exp_freq_table[i[0]]*exp_freq_table[i[1]]
    exp_freq_mat.mat_type = EXPFREQ
    return exp_freq_mat
#
# Build the substitution matrix
#
def _build_subs_mat(obs_freq_mat,exp_freq_mat):
    """ Build the substitution matrix """
    if obs_freq_mat.ab_list <> exp_freq_mat.ab_list:
        raise ValueError, "Alphabet mismatch in passed matrices"
    subs_mat = SeqMat(obs_freq_mat)
    for i in obs_freq_mat.keys():
        subs_mat[i] = obs_freq_mat[i]/exp_freq_mat[i]

    subs_mat.mat_type = SUBS
    return subs_mat

#
# Build a log-odds matrix
#
def _build_log_odds_mat(subs_mat,logbase=10,factor=10.0,round_digit=0):
    """_build_log_odds_mat(subs_mat,logbase=10,factor=10.0,roundit=1):
    Build a log-odds matrix
    logbase=10: base of logarithm used to build (default 10)
    factor=10.: a factor by which each matrix entry is multiplied
    roundit=1: TRUE: round off matrix value.
    """
    lo_mat = SeqMat(subs_mat)
    for i in subs_mat.keys():
        lo_mat[i] = round(factor*log(subs_mat[i])/log(logbase),round_digit)

    lo_mat.mat_type = LO
    return lo_mat

#
# External function. User provides an accepted replacement matrix, and,
# optionally the following: expected frequency table, log base, mult. factor,
# and rounding factor. Generates a log-odds matrix, calling internal SubsMat
# functions.
#
def make_log_odds_matrix(acc_rep_mat,exp_freq_table=None,logbase=10,
                          factor=10.0,round_digit=0):
    obs_freq_mat = _build_obs_freq_mat(acc_rep_mat)
    if not exp_freq_table:
        exp_freq_table = _exp_freq_table_from_obs_freq(obs_freq_mat)
    exp_freq_mat = _build_exp_freq_mat(exp_freq_table)
    subs_mat = _build_subs_mat(obs_freq_mat, exp_freq_mat)
    lo_mat = _build_log_odds_mat(subs_mat,logbase,factor,round_digit)
    return lo_mat
