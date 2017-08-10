# Ansible Modules

Some custom ansible modules not yet submitted or accepted by [Ansible](https://github.com/ansible/ansible).

## Usage

#### cloudformation_diff

An Ansible module that will show the differences that would occur in case you actually run [cloudformation_module](http://docs.ansible.com/ansible/latest/cloudformation_module.html). Changes to be shown include:

1. Stack template changes
2. Stack parameter changes
3. Stack tag changes

Changes that can be omitted by the module:

1. Stack template description
2. Stack parameters that use `NoEcho: true`

The diff output can be in `json` or `yaml` depending on your preferred choice to view the diff.

**Options**

| Parameter | Required | Default | Choices | Comments |
|-----------|----------|---------|---------|----------|
| aws_access_key | no  |         |         | AWS access key. If not set then the value of the AWS_ACCESS_KEY_ID, AWS_ACCESS_KEY or EC2_ACCESS_KEY environment variable is used. |
| aws_secret_key | no  |         |         | AWS secret key. If not set then the value of the AWS_SECRET_ACCESS_KEY, AWS_SECRET_KEY, or EC2_SECRET_KEY environment variable is used. |
| ec2_url   | no       |         |         | Url to use to connect to EC2 or your Eucalyptus cloud (by default the module will use EC2 endpoints). Ignored for modules where region is required. Must be specified for all other modules if region is not used. If not set then the value of the EC2_URL environment variable, if any, is used. |
| profile   | no       |         |         | Uses a boto profile. Only works with boto >= 2.24.0. |
| region    | no       |         |         | The AWS region to use. If not specified then the value of the AWS_REGION or EC2_REGION environment variable, if any, is used. See http://docs.aws.amazon.com/general/latest/gr/rande.html#ec2_region |
| security_token | no  |         |         | AWS STS security token. If not set then the value of the AWS_SECURITY_TOKEN or EC2_SECURITY_TOKEN environment variable is used. |
| stack_name     | yes |         |         | Name of the cloudformation stack |
| template       | yes |         |         | Path to local cloudformation template file (yaml or json) |
| template_parameters | no |     |         | Dict of variable template parameters to add to the stack. |
| template_tags  | no  |         |         | Dict of tags to asign to the stack. |
| ignore_template_desc | no | no | `yes` or `no` | In template diff mode, ignore the template description |
| ignore_hidden_params | no | no | `yes` or `no` | In parameter diff mode, ignore any template parameters with 'NoEcho: true' |
| ignore_final_newline | no | no | `yes` or `no` | In all diff modes, remove any trailing newline (\n or \r) |
| output_format  | no  | json | `json` or `yaml` | Specify in what format to view the diff output ('json' or 'yaml') |
| output_choice  | no  | template | `template`, `parameters` or `tags` | Specify what to diff ('template', 'parameters' or 'tags') |
| validate_certs | no  | yes     | `yes` or `no` | When set to "no", SSL certificates will not be validated for boto versions >= 2.6.0. |

**How to run**

```shell
# Ansible dry-run to see what would change
$ ansible-playbook cfn-playbook.yml --diff --check
```

**Task Examples**

```yaml
# By using the following:
#   when: ansible_check_mode
#   check_mode: no
# you can make sure to only run the cloudformation_diff in ansible --check mode
# to view the diff, you must also specify --diff

# Get changes for the template only and ignore
# the template description.
# Local stack file can be json or yaml.
# Diff is shown in yaml.
- name: "diff Cloudformation template: {{ cfn_stack_name }}"
  cloudformation_diff:
    region: "us-east-1"
    stack_name: "{{ cfn_stack_name }}"
    template: "{{ cfn_template }}"
    template_parameters: "{{ cfn_template_parameters }}"
    template_tags: "{{ cfn_tags|default(omit) }}"
    ignore_template_desc: yes
    output_choice: template
    output_format: yaml
  when: ansible_check_mode
  check_mode: no

# Get changes for the parameters and ignore any
# NoEcho: true parameters.
# Local stack file can be json or yaml.
# Diff is shown in json.
- name: "diff Cloudformation template params: {{ cfn_stack_name }}"
  cloudformation_diff:
    region: "us-east-1"
    stack_name: "{{ cfn_stack_name }}"
    template: "{{ cfn_template }}"
    template_parameters: "{{ cfn_template_parameters }}"
    template_tags: "{{ cfn_tags|default(omit) }}"
    ignore_hidden_params: yes
    output_choice: parameter
    output_format: json
  when: ansible_check_mode
  check_mode: no

# Get changes for the tags.
# Local stack file can be json or yaml.
# Diff is shown in json.
- name: "diff Cloudformation template tags: {{ cfn_stack_name }}"
  cloudformation_diff:
    region: "us-east-1"
    stack_name: "{{ cfn_stack_name }}"
    template: "{{ cfn_template }}"
    template_parameters: "{{ cfn_template_parameters }}"
    template_tags: "{{ cfn_tags|default(omit) }}"
    output_choice: tags
    output_format: json
  when: ansible_check_mode
  check_mode: no
```


## Integration

> Assuming you are in the root folder of your ansible project.

Specify a module path in your ansible configuration file.

```shell
$ vim ansible.cfg
```
```ini
[defaults]
...
library = ./library
...
```

Create the directory and copy the python modules into that directory

```shell
$ mkdir library
$ cp path/to/module library
```

