# JS Action with Pre and Post steps

This action executes main, pre and post scripts provided as inputs irrespective of the main script result.

## Inputs

### `command`

**Required** Main bash script executed by the step. Default `echo "WARNING - main command not set"`.

### `pre-command`

**Optional** Pre bash script executed by the step.

### `post-command`

**Required** Post bash script executed by the step. Default `echo "WARNING - post command not set"`.

## Example usage

```yaml
uses: ./.github/actions/pre_post_action
with:
  pre-command: |
    echo "Hello from pre script"
  command: |
    echo "Hello from main script"
  post-command: |
    echo "Hello from post script"
```
