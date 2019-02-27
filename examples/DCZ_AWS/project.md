DCZ for AWS
===========

Simple automatic provisioning of AWS things managed with a DCZ.
For the esample to work, a properly configured AWS Account must be present:

* IAM credentials of a user with access to IoT Core
* an IoT Policy to enable device connection and publishing


```
# example device policy
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "iot:Connect",
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": "iot:Publish",
      "Resource": "arn:aws:iot:<your-aws-region>:<your-aws-account-number>:topic/dev/sample"
    }
  ]
}

```
