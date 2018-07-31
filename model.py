"""
Implementation of VGGNet, from paper
"""
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.utils import data
import torchvision.datasets as datasets
import torchvision.transforms as transforms
from tensorboardX import SummaryWriter

# define pytorch device - useful for device-agnostic execution
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# define model parameters based on original paper
NUM_EPOCHS = 74
BATCH_SIZE = 256
MOMENTUM = 0.9
LR_INIT = 0.01
IMAGE_DIM = 224  # pixels
NUM_CLASSES = 1000  # 1000 classes for imagenet 2012
DEVICE_IDS = [0, 1]  # GPUs to use
# modify this to point to your data directory
INPUT_ROOT_DIR = 'vggnet_data_in'
TRAIN_IMG_DIR = 'vggnet_data_in/imagenet'
OUTPUT_DIR = 'vggnet_data_out/tblogs'  # tensorboard logs


class AlexNet(nn.Module):
    """
    Neural network model consisting of layers propsed by AlexNet paper.
    """
    def __init__(self, num_classes=1000):
        """
        Define and allocate layers for this neural net.

        Args:
            num_classes (int): number of classes to predict with this model
        """
        super().__init__()
        # input size should be : (b x 3 x 224 x 224)
        self.net = nn.Sequential(
            nn.Conv2d(
                in_channels=3, out_channels=64, kernel_size=3, stride=1, padding=1),  # (b x 64 x 224 x 224)
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 64, 3, 1, 1),  # (b x 64 x 224 x 224)
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),  # (b x 64 x 112 x 112)

            nn.Conv2d(64, 128, 3, 1, 1),  # (b x 128 x 112 x 112)
            nn.ReLU(inplace=True),
            nn.Conv2d(128, 128, 3, 1, 1),  # (b x 128 x 112 x 112)
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),  # (b x 64 x 56 x 56)

            nn.Conv2d(128, 256, 3, 1, 1),  # (b x 256 x 56 x 56)
            nn.ReLU(inplace=True),
            nn.Conv2d(256, 256, 3, 1, 1),  # (b x 256 x 56 x 56)
            nn.ReLU(inplace=True),
            nn.Conv2d(256, 256, 3, 1, 1),  # (b x 256 x 56 x 56)
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),  # (b x 256 x 28 x 28)

            nn.Conv2d(256, 512, 3, 1, 1),  # (b x 512 x 28 x 28)
            nn.ReLU(inplace=True),
            nn.Conv2d(512, 512, 3, 1, 1),  # (b x 512 x 28 x 28)
            nn.ReLU(inplace=True),
            nn.Conv2d(512, 512, 3, 1, 1),  # (b x 512 x 28 x 28)
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),  # (b x 512 x 14 x 14)

            nn.Conv2d(512, 512, 3, 1, 1),  # (b x 512 x 14 x 14)
            nn.ReLU(inplace=True),
            nn.Conv2d(512, 512, 3, 1, 1),  # (b x 512 x 14 x 14)
            nn.ReLU(inplace=True),
            nn.Conv2d(512, 512, 3, 1, 1),  # (b x 512 x 14 x 14)
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),  # (b x 512 x 7 x 7)
        )
        # classifier is just a name for linear layers
        self.classifier = nn.Sequential(
            nn.Linear(in_features=(512 * 7 * 7), out_features=4096),
            nn.Dropout(p=0.5, inplace=True),
            nn.ReLU(),
            nn.Linear(in_features=4096, out_features=4096),
            nn.Dropout(p=0.5, inplace=True),
            nn.ReLU(),
            nn.Linear(in_features=4096, out_features=num_classes),
        )

    def forward(self, x):
        """
        Pass the input through the net.

        Args:
            x (Tensor): input tensor

        Returns:
            output (Tensor): output tensor
        """
        x = self.net(x)
        x = x.view(-1, 512 * 7 * 7)  # reduce the dimensions for linear layer input
        return self.classifier(x)


def init_weights(m):
    if isinstance(m, nn.Conv2d):
        nn.init.normal_(m.weight, mean=0, std=0.1)
        nn.init.constant_(m.bias, 0)


if __name__ == '__main__':
    # create model
    alexnet = AlexNet(num_classes=NUM_CLASSES).to(device)
    # train on multiple GPUs
    alexnet = torch.nn.parallel.DataParallel(alexnet, device_ids=DEVICE_IDS)
    alexnet.apply(init_weights)
    print(alexnet)
    print('AlexNet created')

    # create dataset and data loader
    dataset = datasets.ImageFolder(TRAIN_IMG_DIR, transforms.Compose([
        transforms.RandomResizedCrop(IMAGE_DIM, scale=(0.9, 1.0), ratio=(0.9, 1.1)),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
    ]))
    print('Dataset created')
    dataloader = data.DataLoader(
        dataset,
        shuffle=True,
        pin_memory=True,
        drop_last=True,
        batch_size=BATCH_SIZE)
    print('Dataloader created')

    # create optimizer
    optimizer = optim.SGD(
        params=alexnet.parameters(),
        lr=LR_INIT,
        momentum=MOMENTUM)
    print('Optimizer created')

    # multiply LR by 1 / 10 after every 30 epochs
    lr_scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=20, gamma=0.1)
    print('LR Scheduler created')

    tbwriter = SummaryWriter(log_dir=OUTPUT_DIR)
    print('TensorboardX summary writer created')

    # criterion defined
    criterion = nn.CrossEntropyLoss()
    print('Criterion defined')

    # start training!!
    print('Starting training...')
    total_steps = 1
    for epoch in range(NUM_EPOCHS):
        lr_scheduler.step()
        for imgs, classes in dataloader:
            imgs, classes = imgs.to(device), classes.to(device)
            optimizer.zero_grad()

            # calculate the loss
            output = alexnet(imgs)
            loss = F.cross_entropy(output, classes)
            # loss = F.nll_loss(F.log_softmax(output, dim=1), target=classes)

            # update the parameters
            loss.backward()
            optimizer.step()

            # log the information and add to tensorboard
            if total_steps % 10 == 0:
                with torch.no_grad():
                    _, preds = torch.max(output, 1)
                    accuracy = torch.sum(preds == classes)

                    print('Epoch: {} \tStep: {} \tLoss: {:.4f} \tAcc: {}'
                        .format(epoch + 1, total_steps, loss.item(), accuracy.item()))
                    tbwriter.add_scalar('loss', loss.item(), total_steps)

            total_steps += 1