"""Tests for neural_compressor benchmark"""
import psutil
import unittest
import os
import numpy as np
import tensorflow as tf
import tempfile
import re
from neural_compressor.adaptor.tf_utils.util import write_graph


def build_benchmark():
    seq = '''
from argparse import ArgumentParser
arg_parser = ArgumentParser(description='Parse args')
arg_parser.add_argument('--input_model', dest='input_model', default='input_model', help='input odel')
args = arg_parser.parse_args()
from neural_compressor.benchmark import fit
from neural_compressor.config import BenchmarkConfig
from neural_compressor.data import Datasets
from neural_compressor.experimental import common
dataset = Datasets('tensorflow')['dummy']((100, 32, 32, 1), label=True)
b_dataloader = common.DataLoader(dataset, batch_size=10)
conf = BenchmarkConfig(warmup=5, iteration=10, cores_per_instance=4, num_of_instance=2)
fit(args.input_model, conf, b_dataloader=b_dataloader)
    '''

    seq1 = '''
from argparse import ArgumentParser
arg_parser = ArgumentParser(description='Parse args')
arg_parser.add_argument('--input_model', dest='input_model', default='input_model', help='input odel')
args = arg_parser.parse_args()
from neural_compressor.benchmark import fit
from neural_compressor.config import BenchmarkConfig
from neural_compressor.data import Datasets
dataset = Datasets('tensorflow')['dummy']((100, 32, 32, 1), label=True)
from neural_compressor.experimental import common
conf = BenchmarkConfig(warmup=5, iteration=10, cores_per_instance=4, num_of_instance=2)
b_dataloader = common.DataLoader(dataset, batch_size=10)
fit(args.input_model, conf, b_dataloader=b_dataloader)
    '''

    # test normal case
    with open('fake.py', "w", encoding="utf-8") as f:
        f.writelines(seq)
    # test batchsize > len(dataset), use first batch
    fake_data_5 = seq.replace('100, 32, 32, 1', '5, 32, 32, 1')
    with open('fake_data_5.py', "w", encoding="utf-8") as f:
        f.writelines(fake_data_5)
    # test batchsize < len(dataset) < 2*batchsize, discard first batch
    fake_data_15 = seq1.replace('100, 32, 32, 1', '15, 32, 32, 1')
    with open('fake_data_15.py', "w", encoding="utf-8") as f:
        f.writelines(fake_data_15)
    # test 2*batchsize < len(dataset) < warmup*batchsize, discard last batch
    fake_data_25 = seq1.replace('100, 32, 32, 1', '25, 32, 32, 1')
    with open('fake_data_25.py', "w", encoding="utf-8") as f:
        f.writelines(fake_data_25)

def build_benchmark2():
    seq = [
        "from argparse import ArgumentParser\n",
        "arg_parser = ArgumentParser(description='Parse args')\n",
        "arg_parser.add_argument('--input_model', dest='input_model', default='input_model', help='input model')\n",
        "args = arg_parser.parse_args()\n",
        "from neural_compressor.benchmark import fit\n"
        "from neural_compressor.data import Datasets\n",
        "dataset = Datasets('tensorflow')['dummy']((5, 32, 32, 1), label=True)\n",

        "from neural_compressor.experimental import common\n",
        "b_dataloader = common.DataLoader(dataset)\n",
        "fit(args.input_model, b_dataloader=b_dataloader)\n"
    ]

    with open('fake2.py', "w", encoding="utf-8") as f:
        f.writelines(seq)


def build_fake_model():
    graph_path = tempfile.mkstemp(suffix='.pb')[1]
    try:
        graph = tf.Graph()
        graph_def = tf.GraphDef()
        with tf.Session(graph=graph) as sess:
            x = tf.placeholder(tf.float64, shape=(None, 32, 32, 1), name='x')
            y_1 = tf.constant(np.random.random((3, 3, 1, 1)), name='y_1')
            y_2 = tf.constant(np.random.random((3, 3, 1, 1)), name='y_2')
            conv1 = tf.nn.conv2d(input=x, filter=y_1, strides=[1, 1, 1, 1], \
                                 padding='VALID', name='conv1')
            op = tf.nn.conv2d(input=conv1, filter=y_2, strides=[1, 1, 1, 1], \
                              padding='VALID', name='op_to_store')

            sess.run(tf.global_variables_initializer())
            constant_graph = tf.graph_util.convert_variables_to_constants(sess, sess.graph_def, ['op_to_store'])

        graph_def.ParseFromString(constant_graph.SerializeToString())
        write_graph(graph_def, graph_path)
    except:
        graph = tf.Graph()
        graph_def = tf.compat.v1.GraphDef()
        with tf.compat.v1.Session(graph=graph) as sess:
            x = tf.compat.v1.placeholder(tf.float64, shape=(None, 32, 32, 1), name='x')
            y_1 = tf.constant(np.random.random((3, 3, 1, 1)), name='y_1')
            y_2 = tf.constant(np.random.random((3, 3, 1, 1)), name='y_2')
            conv1 = tf.nn.conv2d(input=x, filters=y_1, strides=[1, 1, 1, 1], \
                                 padding='VALID', name='conv1')
            op = tf.nn.conv2d(input=conv1, filters=y_2, strides=[1, 1, 1, 1], \
                              padding='VALID', name='op_to_store')

            sess.run(tf.compat.v1.global_variables_initializer())
            constant_graph = tf.compat.v1.graph_util.convert_variables_to_constants(sess, sess.graph_def, ['op_to_store'])

        graph_def.ParseFromString(constant_graph.SerializeToString())
        write_graph(graph_def, graph_path)
    return graph_path

class TestObjective(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.graph_path = build_fake_model()
        build_benchmark()
        build_benchmark2()
        self.cpu_counts = psutil.cpu_count(logical=False)

    @classmethod
    def tearDownClass(self):
        if os.path.exists('fake.py'):
            os.remove('fake.py')
        if os.path.exists('fake2.py'):
            os.remove('fake2.py')
        if os.path.exists('fake_data_5.py'):
            os.remove('fake_data_5.py')
        if os.path.exists('fake_data_15.py'):
            os.remove('fake_data_15.py')
        if os.path.exists('fake_data_25.py'):
            os.remove('fake_data_25.py')

    def test_benchmark(self):
        os.system("python fake.py --input_model={}".format(self.graph_path))
        for i in range(2):
            with open(f'2_4_{i}.log', "r") as f:
                for line in f:
                    throughput = re.search(r"Throughput:\s+(\d+(\.\d+)?) images/sec", line)
                self.assertIsNotNone(throughput)
        os.system("rm *.log")

    def test_benchmark_data_5(self):
        os.system("python fake_data_5.py --input_model={}".format(self.graph_path))
        for i in range(2):
            with open(f'2_4_{i}.log', "r") as f:
                for line in f:
                    throughput = re.search(r"Throughput:\s+(\d+(\.\d+)?) images/sec", line)
                self.assertIsNotNone(throughput)
        os.system("rm *.log")

    def test_benchmark_data_15(self):
        os.system("python fake_data_15.py --input_model={}".format(self.graph_path))
        for i in range(2):
            with open(f'2_4_{i}.log', "r") as f:
                for line in f:
                    throughput = re.search(r"Throughput:\s+(\d+(\.\d+)?) images/sec", line)
                self.assertIsNotNone(throughput)
        os.system("rm *.log")

    def test_benchmark_data_25(self):
        os.system("python fake_data_25.py --input_model={}".format(self.graph_path))
        for i in range(2):
            with open(f'2_4_{i}.log', "r") as f:
                for line in f:
                    throughput = re.search(r"Throughput:\s+(\d+(\.\d+)?) images/sec", line)
                self.assertIsNotNone(throughput)
        os.system("rm *.log")


if __name__ == "__main__":
    unittest.main()
