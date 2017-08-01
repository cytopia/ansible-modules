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

```yaml
# By using the following:
#   when: ansible_check_mode
#   check_mode: no
# you can make sure to only run the cloudformation_diff in ansible --check mode
# to view the diff, you must also specify --diff

- name: "diff Cloudformation template: {{ cfn_stack_name }}"
  cloudformation_diff:
    stack_name: "{{ cfn_stack_name }}"
    template: "{{ cfn_template }}"
    template_parameters: "{{ cfn_template_parameters }}"
    template_tags: "{{ cfn_tags|default(omit) }}"
    ignore_template_desc: yes
    output_choice: template
    output_format: yaml
  when: ansible_check_mode
  check_mode: no

- name: "diff Cloudformation template params: {{ cfn_stack_name }}"
  cloudformation_diff:
    stack_name: "{{ cfn_stack_name }}"
    template: "{{ cfn_template }}"
    template_parameters: "{{ cfn_template_parameters }}"
    template_tags: "{{ cfn_tags|default(omit) }}"
    ignore_hidden_params: yes
    output_choice: parameter
    output_format: json
  when: ansible_check_mode
  check_mode: no

- name: "diff Cloudformation template tags: {{ cfn_stack_name }}"
  cloudformation_diff:
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
