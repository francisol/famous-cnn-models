import tensorflow as tf
from datetime import datetime
import numpy as np

from utils.load_image_net_224x224x3 import (
    X_train, X_test, X_validation,
    y_train, y_test, y_validation
)


class GoogLeNet(object):

    def __init__(self, learning_rate=0.001, num_epochs=10, batch_size=100):
        self.num_classes = np.shape(y_train)[1]
        # Input & output placeholders
        self.X = tf.placeholder(dtype=tf.float32, shape=(None, 224, 224, 3), name='image')
        self.y = tf.placeholder(dtype=tf.float32, shape=(None, self.num_classes), name='label')
        # Training process related params
        self.learning_rate = learning_rate
        self.num_epochs = num_epochs
        self.batch_size = batch_size

    @staticmethod
    def inception(inputs, conv_11_size, conv_33_reduce_size, conv_33_size,
                  conv_56_reduce_size, conv_56_size, pool_proj_size):
        """ Apply inception processing to input tensor.

        An inception layer consists of 4 individual parts and a final concatenation of them

                       Concatenation                            - Path 1:
                    /     /     \     \                             a) 1 * 1 Convolutional
                  /      /       \       \
                /       /         \         \                   - Path 2:
        1 * 1 Conv  3 * 3 Conv  5 * 5 Conv  1 * 1 Conv              a) 1 * 1 Convolutional
            |           |           |          |                    b) 3 * 3 Convolutional
             \          |           |          |
              \     1 * 1 Conv  1 * 1 Conv  3 * 3 Pool          - Path 3:
                \       |         /       /                         a) 1 * 1 Convolutional
                  \     |      /      /                             b) 5 * 5 Convolutional
                    \   |    /     /
                      \ |  /   /                                - Path 4:
                        Inputs                                      a) 3 * 3 Max Pooling
                                                                    b) 1 * 1 Convolutional

        Args:
            inputs: (Tensor) -- Input tensor
            conv_11_size: (int) -- Output dimension of Path 1 ( conv 1 * 1 )
            conv_33_reduce_size: (int) -- Output dimension of Path 2a ( conv 1 * 1 )
            conv_33_size: (int) -- Output dimension of Path 2b ( conv 3 * 3 )
            conv_56_reduce_size: (int) -- Output dimension of Path 3a ( conv 1 * 1 )
            conv_56_size: (int) -- Output dimension of Path 3b ( conv 5 * 5 )
            pool_proj_size: (int) -- Output dimension of Path 4b ( conv 1 * 1 )

        Returns:
            concat: (Tensor) -- Output tensor of inception layer
        """
        # Path 1
        conv_11 = tf.layers.conv2d(inputs, filters=conv_11_size, kernel_size=[1, 1], padding='same')

        # Path 2
        conv_33_reduce = tf.layers.conv2d(inputs, filters=conv_33_reduce_size, kernel_size=[1, 1], padding='same')
        conv_33 = tf.layers.conv2d(conv_33_reduce, filters=conv_33_size, kernel_size=[3, 3], padding='same')

        # Path 3
        conv_56_reduce = tf.layers.conv2d(inputs, filters=conv_56_reduce_size, kernel_size=[1, 1], padding='same')
        conv_56 = tf.layers.conv2d(conv_56_reduce, filters=conv_56_size, kernel_size=[5, 5], padding='same')

        # Path 4
        pool = tf.layers.max_pooling2d(inputs, pool_size=[3, 3], strides=1, padding='same')
        conv_pool = tf.layers.conv2d(pool, filters=pool_proj_size, kernel_size=[1, 1], padding='same')

        # Concatenation
        return tf.concat([conv_11, conv_33, conv_56, conv_pool], 3)

    def auxiliary(self, inputs):
        """ Auxiliary classifier layer of GoogLeNet

                                   GoogLeNet Continues ...
                                 /
        ... -> Output of Inception Layer
                            \
                     + - - - \ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - +
                     |        \                             (auxiliary part)                     |
                     |         \                                                                 |
                     |        pool - conv - flatten - dense(dropout) - dense - softmax logits    |
                     + - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - +
        """
        pool = tf.layers.average_pooling2d(inputs, [5, 5], strides=3, padding='same')
        conv = tf.layers.conv2d(pool, filters=128, kernel_size=[1, 1])
        flat = tf.layers.flatten(conv)
        full = tf.layers.dense(flat, units=1024)
        drop = tf.layers.dropout(full, 0.3)
        return tf.layers.dense(drop, self.num_classes, activation=None)

    def run(self):
        """
        Run forward/backward propagation on GoogLeNet (Inception-v1)

        # 1st Convolutional Layer:  Input 224 * 224 *  3 ,    Output  56 *  56 * 64
        #   - a) Convolution        Input 224 * 224 *  3 ,    Output 114 * 114 * 64
        #   - b) Subsampling        Input 114 * 114 * 64 ,    Output  56 *  56 * 64
        #   - c) Normalization      Input  56 *  56 * 64 ,    Output  56 *  56 * 64

        # 2nd Convolutional Layer:  Input  56 * 56 *  64 ,    Output 13 * 13 * 256
        #   - a) Convolution a      Input  56 * 56 *  64 ,    Output 56 * 56 *  64
        #   - b) Convolution b      Input  56 * 56 *  64 ,    Output 56 * 56 * 192
        #   - c) Normalization      Input  56 * 56 * 192 ,    Output 56 * 56 * 192
        #   - d) Subsampling        Input  56 * 56 * 192 ,    Output 28 * 28 * 192

        # 3rd Inception Layer:      Input  28 * 28 * 192 ,    Output 28 * 28 * 480
        #   - a) Inception a        Input  28 * 28 * 192 ,    Output 28 * 28 * 256
        #   - b) Inception b        Input  28 * 28 * 256 ,    Output 28 * 28 * 480
        #   - c) Subsampling        Input  28 * 28 * 480 ,    Output 14 * 14 * 480

        # 4.1 Inception Layer:      Input  14 * 14 * 480 ,    Output 14 * 14 * 832
        #   - a) Inception a        Input  14 * 14 * 480 ,    Output 14 * 14 * 512
        #   - b) Inception b        Input  14 * 14 * 512 ,    Output 14 * 14 * 512
        #   - c) Inception c        Input  14 * 14 * 512 ,    Output 14 * 14 * 512
        #   - d) Inception d        Input  14 * 14 * 512 ,    Output 14 * 14 * 528
        #   - e) Inception e        Input  14 * 14 * 528 ,    Output 14 * 14 * 832
        #   - f) Max Pooling        Input  14 * 14 * 832 ,    Output  7 *  7 * 832

        # 4.2 Auxiliary Layer:      Input  14 * 14 * 480 ,    Output 14 * 14 * 832
        #   - 4a -> auxiliary_1     Input  14 * 14 * 512 ,    Output self.num_classes
        #   - 4d -> auxiliary_2     Input  14 * 14 * 528 ,    Output self.num_classes

        # 5th Inception Layer:      Input   7 *  7 * 832 ,    Output 1 * 1 * 1024
        #   - a) Inception a        Input   7 *  7 * 832 ,    Output 7 * 7 *  832
        #   - b) Inception b        Input   7 *  7 * 832 ,    Output 7 * 7 * 1024
        #   - c) Avg Pooling        Input   7 *  7 * 1024,    Output 1 * 1 * 1024

        # 6th Full Connect Layer:   Input   1 *  1 * 1024,    Output  self.num_classes
        #   - a) Flatten            Input   1 *  1 * 1024,    Output 1024
        #   - b) Dropout            Input            1024,    Output 1024
        #   - c) Dense              Input            1024,    Output 1024
        """

        ##########################################################################
        # Forward propagation
        ##########################################################################

        # 1st Convolutional Layer
        conv_1 = tf.layers.conv2d(self.X, filters=64, kernel_size=[7, 7], strides=[2, 2], padding='same')
        pool_1 = tf.layers.max_pooling2d(conv_1, pool_size=[3, 3], strides=[2, 2], padding='same')
        norm_1 = tf.nn.local_response_normalization(pool_1, depth_radius=2.0, bias=1.0, alpha=2e-4, beta=0.75)

        # 2nd Convolutional Layer
        conv_2a = tf.layers.conv2d(norm_1, filters=64, kernel_size=[1, 1], padding='same')
        conv_2b = tf.layers.conv2d(conv_2a, filters=192, kernel_size=[3, 3], padding='same')
        norm_2 = tf.nn.local_response_normalization(conv_2b, depth_radius=2.0, bias=1.0, alpha=2e-4, beta=0.75)
        pool_2 = tf.layers.max_pooling2d(norm_2, pool_size=[3, 3], strides=[2, 2], padding='same')

        # 3rd Inception Layer
        inception_3a = self.inception(pool_2, conv_11_size=64,
                                      conv_33_reduce_size=96, conv_33_size=128,
                                      conv_56_reduce_size=16, conv_56_size=32,
                                      pool_proj_size=32)
        inception_3b = self.inception(inception_3a, conv_11_size=128,
                                      conv_33_reduce_size=128, conv_33_size=192,
                                      conv_56_reduce_size=32, conv_56_size=96,
                                      pool_proj_size=64)
        pool_3 = tf.layers.max_pooling2d(inception_3b, pool_size=[3, 3], strides=[2, 2], padding='same')

        # 4.1 Inception Layer
        inception_4a = self.inception(pool_3, 192, 96, 208, 16, 48, 64)
        inception_4b = self.inception(inception_4a, 160, 112, 224, 24, 64, 64)
        inception_4c = self.inception(inception_4b, 128, 128, 256, 24, 64, 64)
        inception_4d = self.inception(inception_4c, 112, 144, 288, 32, 64, 64)
        inception_4e = self.inception(inception_4d, 256, 160, 320, 32, 128, 128)
        pool_4 = tf.layers.max_pooling2d(inception_4e, pool_size=[3, 3], strides=[2, 2], padding='same')
        # 4.2 Auxiliary Layer
        auxiliary_1 = self.auxiliary(inception_4a)
        auxiliary_2 = self.auxiliary(inception_4d)

        # 5th Inception Layer
        inception_5a = self.inception(pool_4, 256, 160, 320, 32, 128, 128)
        inception_5b = self.inception(inception_5a, 384, 192, 384, 48, 128, 128)
        pool_5 = tf.layers.average_pooling2d(inception_5b, pool_size=[7, 7], strides=[1, 1])

        # 6th Full Connected Layer
        flat_5 = tf.layers.flatten(pool_5)
        drop_6 = tf.layers.dropout(flat_5, rate=0.4)
        linear = tf.layers.dense(drop_6, units=self.num_classes)

        ##########################################################################
        # Backward propagation
        ##########################################################################

        cross_entropy = tf.nn.softmax_cross_entropy_with_logits_v2(labels=self.y, logits=linear)
        loss = tf.reduce_mean(cross_entropy)
        optimizer = tf.train.AdamOptimizer(self.learning_rate)
        train = optimizer.minimize(loss)

        ##########################################################################
        # Compute accuracy
        ##########################################################################

        corrects = tf.equal(tf.round(linear), tf.round(self.y))
        accuracy = tf.reduce_mean(tf.cast(corrects, tf.float32))

        ##########################################################################
        # Train the network
        ##########################################################################

        sess = tf.Session()

        sess.run(tf.global_variables_initializer())

        print()
        print(datetime.now(), 'Training GoogLeNet model')

        for i in range(self.num_epochs):
            for start in range(0, len(X_train), self.batch_size):
                end = start + self.batch_size
                batch_X, batch_y = X_train[start:end], y_train[start:end]
                sess.run(train, feed_dict={
                    self.X: batch_X, self.y: batch_y})
                if end % 100 == 0:
                    print('{} Training Epoch {} {}/{}'.format(datetime.now(), i, end, len(X_train)))

            # Show loss on validation dataset when finishing each epoch
            print('\n{} Training Epoch: {} Loss: {} Accuracy: {}\n'.format(
                datetime.now(), i,
                *sess.run(
                    (loss, accuracy),
                    feed_dict={self.X: X_validation, self.y: y_validation}))
            )

        ##########################################################################
        # Compute accuracy on test set
        ##########################################################################

        # Evaluate on test set
        print(datetime.now(), 'Evaluating GoogLeNet model on test set')
        print('\n{} Test Result: Loss: {} Accuracy: {}\n'.format(
            datetime.now(), *sess.run(
                (loss, accuracy),
                feed_dict={self.X: X_test, self.y: y_test}))
        )

        sess.close()


if __name__ == '__main__':
    net = GoogLeNet()
    net.run()
