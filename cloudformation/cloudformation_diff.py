#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2017, cytopia <cytopia@everythingcli.org>
#
# This module is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.
#

ANSIBLE_METADATA = {'metadata_version': '1.0',
                    'supported_by': 'community',
                    'status': ['preview']}

DOCUMENTATION = '''
---
module: cfndiff
short_description: Diff compares two cloudformation templates regardless of being json or yaml.
description:
     -  Compares two cloudformation templates which both can have equal or different formats (json or yaml). If the files differ, their diff will be printed in C(--diff) mode and the module marks its run as C(changed).
version_added: 2.3
options:
  lft:
    description:
      - Original cfn template file path
      - Can be a json or yaml file
    required: true
    default: null
    aliases: []
  rgt:
    description:
      - New cfn template file path
      - Can be a json or yaml file
    required: true
    default: null
    aliases: []
  format:
    required: false
    choices: [ json, yaml ]
    default: "yaml"
    aliases: []
    description:
      - Diff returned in either json or yaml format. (defaults to yaml)
requirements:
   - cfn_flip python module: C(pip install cfn_flip)
author: cytopia (@cytopia)
notes:
  - The "cfndiff" compares (diffs) two cloudformation template files regardless of being json or yaml.
'''
EXAMPLES = '''
#
# Create a dry-run (faked with --check mode) for cloudformation templates
#
- name: get upstream cloudformation stack template for vpc-prod
  cloudformation_facts:
    stack_name: vpc-prod
    stack_template: yes
  register: reg_cfn_template
  failed_when: False
  when: ansible_check_mode
  check_mode: no

- name: copy remote stack content into temporary file
  copy:
    content: "{{ reg_cfn_template['ansible_facts']['cloudformation']['vpc-prod']['stack_template'] }}"
    dest: /tmp/vpc-prod.yml
  changed_when: False
  when: ansible_check_mode
  check_mode: no

# Compare current local vs remotely applied version
- cfndiff:
    lft: /tmp/vpc-prod.yml
    rgt: files/vpc-prod.yml
    format: yaml
  when: ansible_check_mode
  check_mode: no
'''

# Python default imports
import os
import json
import traceback
from collections import OrderedDict
from functools import partial

# Python Custom libraries
# requires 'cfn_flip'
# $ pip install cfn_flip
from cfn_flip import flip, to_yaml, to_json

try:
    import boto3
    import botocore
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

# Python Ansible imports
from ansible.module_utils.ec2 import get_aws_connection_info, ec2_argument_spec, boto3_conn, camel_dict_to_snake_dict
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_bytes, to_native


################################################################################
#
#  C L A S S E S
#
################################################################################

class CloudFormationServiceManager:
    '''
    Handles CloudFormation Services
    Partly copied from cloudformation_facts module.
    '''

    def __init__(self, module):
        self.module = module

        try:
            region, ec2_url, aws_connect_kwargs = get_aws_connection_info(module, boto3=True)
            self.client = boto3_conn(module, conn_type='client',
                                     resource='cloudformation', region=region,
                                     endpoint=ec2_url, **aws_connect_kwargs)
        except botocore.exceptions.NoRegionError:
            self.module.fail_json(msg="Region must be specified as a parameter, in AWS_DEFAULT_REGION environment variable or in boto configuration file")
        except Exception as e:
            self.module.fail_json(msg="Can't establish connection - " + str(e), exception=traceback.format_exc())

    def describe_stack(self, stack_name):
        try:
            func = partial(self.client.describe_stacks,StackName=stack_name)
            response = self.paginated_response(func, 'Stacks')
            if response:
                return response[0]
            self.module.fail_json(msg="Error describing stack - an empty response was returned")
        except Exception as e:
            #self.module.fail_json(msg="Error describing stack - " + str(e), exception=traceback.format_exc())
            # Do not raise an erroy here, but return an empty response.
            # We will take care about this in a later stage in the module run.
            return dict()

    def get_template(self, stack_name):
        try:
            response = self.client.get_template(StackName=stack_name)
            return response.get('TemplateBody')
        except Exception as e:
            #self.module.fail_json(msg="Error getting stack template - " + str(e), exception=traceback.format_exc())
            # Do not raise an erroy here, but return an empty response.
            # We will take care about this in a later stage in the module run.
            return dict()

    def paginated_response(self, func, result_key, next_token=None):
        '''
        Returns expanded response for paginated operations.
        The 'result_key' is used to define the concatenated results that are combined from each paginated response.
        '''
        args=dict()
        if next_token:
            args['NextToken'] = next_token
        response = func(**args)
        result = response.get(result_key)
        next_token = response.get('NextToken')
        if not next_token:
            return result
        return result + self.paginated_response(func, result_key, next_token)


class SortedDict(OrderedDict):
    '''
    This class adds a custom recursive JSON sorter.
    JSON dicts are sorted recursively and alphabetically by key.
    '''
    def __init__(self, **kwargs):
        super(SortedDict, self).__init__()

        for key, value in sorted(kwargs.items()):
            if isinstance(value, dict):
                self[key] = SortedDict(**value)
            else:
                self[key] = value


################################################################################
#
#  G E N E R I C   F U N C T I O N S
#
################################################################################

def quote_json(obj):
    '''
    Treat all json key/values as strings and therefore
    quote them to be consistent
    '''
    if type(obj) in (bool, str, int, float, long, complex):
        return str(obj)
    if isinstance(obj, (list, tuple)):
        return [quote_json(item) for item in obj]
    if isinstance(obj, dict):
        return {quote_json(key):quote_json(value) for key, value in obj.items()}
    return obj


def to_dict(items, key, value):
    '''
    Transforms a list of items to a Key/Value dictionary
    Partly copied from cloudformation_facts module.
    '''
    if items:
        return dict(zip([i[key] for i in items], [i[value] for i in items]))
    else:
        return dict()


################################################################################
#
#  C F N D I F F   F U N C T I O N S
#
################################################################################

def cfn_get_noecho_param_names(items):
    '''
    Get a list of all parameter names which have 'NoEcho = true'.
    '''
    if items:
        data = []
        for i in items:
            if 'NoEcho' in items[i]:
                if str(items[i]['NoEcho']).lower() == 'true':
                    data.append(i)
        return data
    else:
        return []


def cfn_get_default_value_params(items):
    '''
    Extract only the parameters from the template item dict
    which have a default value defined.
    Extraction form: { "<param-name>": "<default-value>", ...}
    '''
    if items:
        data = {}
        for i in items:
            if 'Default' in items[i]:
                data[i] = items[i]['Default']
        return data
    else:
        return dict()


def get_json_or_yaml(data, output_format='json'):
    '''
    Convert into json or yaml from
    json or yaml.
    '''

    # Make all dicts a string first
    if isinstance(data, dict):
        data = json.dumps(data)

    # Get JSON, no matter what input (yaml or json)
    try:
        data = to_json(data)
    except ValueError:
        data = to_yaml(data)
        data = to_json(data)


    # Create python dict
    data = json.loads(data)

    # Sort python dict
    data = SortedDict(**data)
    data = quote_json(data)

    # Return json or yaml
    if output_format == 'yaml':
        data = to_yaml(json.dumps(data))

    return data


def cfndiff_module_validation(module):
    '''
    Validate for correct module call/usage in ansible.
    '''
    # Boto3 is required!
    if not HAS_BOTO3:
        module.fail_json(msg='boto3 is required.')

    template = module.params['template']
    b_template = to_bytes(template, errors='surrogate_or_strict')

    # Validate path of template
    if not os.path.exists(b_template):
        module.fail_json(msg="template %s not found" % (template))
    if not os.access(b_template, os.R_OK):
        module.fail_json(msg="template %s not readable" % (template))
    if os.path.isdir(b_template):
        module.fail_json(msg="diff does not support recursive diff of directory: %s" % (template))

    return module


def main():
    '''
    cfndiff main entry point.
    '''
    # Ansible module input parameter
    module = AnsibleModule(
        argument_spec = dict(
            stack_name=dict(required=True, type='str'),
            template=dict(required=True, type='path'),
            template_parameters=dict(required=False, type='dict', default={}),
            template_tags=dict(required=False, type='dict', default={}),
            ignore_template_desc=dict(required=False, type='bool', default=False),
            ignore_hidden_params=dict(required=False, type='bool', default=False),
            output_format=dict(required=False, default='json', choices=['json', 'yaml']),
            output_choice=dict(required=False, default='template', choices=['template', 'parameter', 'tags']),
        ),
        # This module should actually only be run in check mode ;-)
        supports_check_mode=True,
    )

    # Validate module
    module = cfndiff_module_validation(module)

    # Get ansible arguments
    stack_name = module.params.get('stack_name')
    output_format = module.params.get('output_format')
    output_choice = module.params.get('output_choice')
    local_params = module.params.get('template_parameters')
    local_tags = module.params.get('template_tags')
    ignore_template_desc = module.params.get('ignore_template_desc')
    ignore_hidden_params = module.params.get('ignore_hidden_params')

    # Get AWS Cloudformation data
    service_mgr = CloudFormationServiceManager(module)
    cloud_data = service_mgr.describe_stack(stack_name)
    cloud_template = service_mgr.get_template(stack_name)
    cloud_output = to_dict(cloud_data.get('Outputs', []), 'OutputKey', 'OutputValue')
    cloud_params = to_dict(cloud_data.get('Parameters', []), 'ParameterKey', 'ParameterValue')
    cloud_tags = to_dict(cloud_data.get('Tags', []), 'Key', 'Value')

    # Get local data
    with open(module.params.get('template'), "rt") as f:
        local_template = f.read().decode("UTF-8")

    # Get diff output
    #
    # 1. Template description does not always update.
    # For example if it is the only change.
    # So the user can request to ignore it.
    if output_choice == 'template':

        if ignore_template_desc == True:
            # Need json Dict for .pop()
            cloud_dict = get_json_or_yaml(cloud_template, 'json')
            local_dict = get_json_or_yaml(local_template, 'json')
            # remove
            cloud_dict.pop('Description', None)
            local_dict.pop('Description', None)
            # Whatever format the user requested
            cloud_dict = get_json_or_yaml(cloud_dict, output_format)
            local_dict = get_json_or_yaml(local_dict, output_format)
        else:
            # Convert to nice yaml/json output
            cloud_dict = get_json_or_yaml(cloud_template, output_format)
            local_dict = get_json_or_yaml(local_template, output_format)

    # 1. Upstream AWS can have more parameters as specified in 'template_parameters'.
    # This is due to the fact, that the template itself has a 'Parameters' section
    # which can have parameters with 'Default' values, that must not explicitly
    # be specified, but still apply.
    #
    # We therefore have to get all Paramters defined in the template itself
    # and merge them with the actual specified parameters.
    # Only template parameters with 'Default' values need to be fetched,
    # all others must be specified anyway.
    #
    # During merge, the explicitly specified parameters must overwrite
    # any template parameters... AWS does the same ;-)
    #
    #
    # 2. There are also parameters which are not shown by Cloudformation.
    # These have 'NoEcho: true' set and only output stars.
    # They will always create a diff/changed output.
    # So we must remove them from the list if ignore_hidden_params is true.
    elif output_choice == 'parameter':
        # Get local paramers from template and parameter definition
        param_params = get_json_or_yaml(local_params, 'json')
        templ_params = get_json_or_yaml(local_template, 'json').get('Parameters')

        # Extract only the template parameters which have a 'Default' value
        templ_def_params = cfn_get_default_value_params(templ_params)

        # Merge parameters from parameters and templates default parametsrs
        # param_params comes 2nd and will overwrite any already available default
        # parameters from the template.
        local_params = templ_def_params.copy()
        local_params.update(param_params)

        if ignore_hidden_params == True:
            hidden_params = cfn_get_noecho_param_names(templ_params)
            cloud_params = get_json_or_yaml(cloud_params, 'json')
            for key in hidden_params:
                local_params.pop(key, None)
                cloud_params.pop(key, None)

        # Convert final local params to nice yaml/json output
        local_dict = get_json_or_yaml(local_params, output_format)
        cloud_dict = get_json_or_yaml(cloud_params, output_format)


    elif output_choice == 'tags':
        # Convert to nice yaml/json output
        cloud_dict = get_json_or_yaml(cloud_tags, output_format)
        local_dict = get_json_or_yaml(local_tags, output_format)


    # Ansible diff output
    diff = {
        'before': cloud_dict,
        'after': local_dict,
    }
    # Did we have any changes?
    changed = (cloud_dict != local_dict)

    # Ansible module returned variables
    result = dict(
        diff = diff,
        changed = changed
    )

    # Exit ansible module call
    module.exit_json(**result)


if __name__ == '__main__':
    main()