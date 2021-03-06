# Contributing to COVIDcast indicator pipelines

## Branches

* `main`

The primary/authoritative branch of this repository is called `main`, and contains up-to-date code and supporting libraries. This should be your starting point when creating a new indicator. It is protected so that only reviewed pull requests can be merged in.

* `deploy-*`

Each automated pipeline has a corresponding branch which automatically deploys to a runtime host which runs the pipeline at a designated time each day. New features and bugfixes are merged into this branch using a pull request, so that our CI system can run the lint and test cycles and make sure the package will run correctly on the runtime host. If an indicator does not have a branch named after it starting with `deploy-`, that means the indicator has not yet been automated, and has a designated human keeper who is responsible for making sure the indicator runs each day -- whether that is manually or using a scheduler like cron is the keeper's choice.

* everything else

All other branches are development branches. We don't enforce a naming policy.

## Issues

Issues are the main communication point when it comes to bugfixes, new features, or other possible changes. The repository has several issue templates that help to structure issues.

If you ensure that each issue deals with a single topic (ie a single new proposed data source, or a single data quality problem), we'll all be less likely to drop subordinate tasks on the floor, but we also recognize that a lot of the people filing issues in this repository are new to large project management and not used to focusing their thoughts in this way. It's okay, we'll all learn and get better together.

Admins will assign issues to one or more people based on balancing expediency, expertise, and team robustness. It may be faster for one person to fix something, but we can reduce the risk of having too many single points of failure if two people work on it together.

## Project Boards

The Delphi Engineering team uses project boards to structure its weekly calls and track active tasks.

Immediate work is tracked on [Release Planning](https://github.com/cmu-delphi/covidcast-indicators/projects/2)

Long-term work and modeling collaborations are tracked on [Refactoring](https://github.com/cmu-delphi/covidcast-indicators/projects/3)


## General workflow for indicators creation and deployment

So, how does one go about developing a pipeline for a new data source?

**tl;dr**

1. Create your new indicator branch from `main`.
2. Build it using the appropriate template, following the guidelines in the included README.md and REVIEW.md files.
3. Make some stuff!
4. When your stuff works, push your `dev-*` branch to remote for review.
5. Consult with a platform engineer for the remaining production setup needs. They will create a branch called `deploy-*` for your indicator.
6. Initiate a pull request against this new branch.
7. Following [the source documentation template](https://github.com/cmu-delphi/delphi-epidata/blob/main/docs/api/covidcast-signals/_source-template.md), create public API documentation for the source. You can submit this as a pull request against the delphi-epidata repository.
8. If your peers like the code, the documentation is ready, and Jenkins approves, deploy your changes by merging the PR.
9. An admin will propagate your successful changes to `main`.
10. Rejoice!

### Starting out

The `main` branch should contain up-to-date code and supporting libraries. This should be your starting point when creating a new indicator.

```shell
# Hint
#
git checkout main
git checkout -b dev-my-feature-branch
```

### Creating your indicator

Create a directory for your new indicator by making a copy of `_template_r` or `_template_python` depending on the programming language you intend to use. The template copies of `README.md` and `REVIEW.md` include the minimum requirements for code structure, documentation, linting, testing, and method of configuration. Beyond that, we don't have any established restrictions on implementation; you can look at other existing indicators see some examples of code layout, organization, and general approach.

- Consult your peers with questions! :handshake:

Once you have something that runs locally and passes tests you set up your remote branch eventual review and production deployment.

```shell
# Hint
#
git push -u origin dev-my-feature-branch
```

You can then draft public API documentation for people who would fetch this
data from the API. Public API documentation is kept in the delphi-epidata
repository, and there is a [template Markdown
file](https://github.com/cmu-delphi/delphi-epidata/blob/main/docs/api/covidcast-signals/_source-template.md)
that outlines the features that need to be documented. You can create a pull
request to add a new file to `docs/api/covidcast-signals/` for your source. Our
goal is to have public API documentation for the data at the same time as it
becomes available to the public.

### Setting up for review and deployment

Once you have your branch set up you should get in touch with a platform engineer to pair up on the remaining production needs. These include:

- Creating the corresponding `deploy-*` branch in the repo.
- Adding the necessary Jenkins scripts for your indicator.
- Preparing the runtime host with any Automation configuration necessities.
- Reviewing the workflow to make sure it meets the general guidelines and will run as expected on the runtime host.

Once all the last mile configuration is in place you can create a pull request against the correct `deploy-*` branch to initiate the CI/CD pipeline which will build, test, and package your indicator for deployment.

If everything looks ok, you've drafted source documentation, platform engineering has validated the last mile, and the pull request is accepted, you can merge the PR. Deployment will start automatically.

Hopefully it'll be a full on :tada:, after that :crossed_fingers:

If not, circle back and try again.

## Production overview

### Running production code

Currently, the production indicators all live and run on the venerable and perennially useful Delphi primary server (also known generically as "the runtime host").

### Delivering an indicator to the production environment

We use a branch-based git workflow coupled with [Jenkins](https://www.jenkins.io/) and [Ansible](https://www.ansible.com/) to build, test, package, and deploy each indicator individually to the runtime host.

- Jenkins dutifully manages the whole process for us by executing several "stages" in the context of a [CI/CD pipeline](https://dzone.com/articles/learn-how-to-setup-a-cicd-pipeline-from-scratch). Each stage does something unique, building on the previous stage. The stages are:
  - Environment - Sets up some environment-specific needs that the other stages depend on.
  - Build - Create the Python venv on the Jenkins host.
  - Test - Run linting and unit tests.
  - Package - Tar and gzip the built environment.
  - Deploy - Trigger an Ansible playbook to place the built package onto the runtime host, place any necessary production configuration, and adjust the runtime envirnemnt (if necessary).

There are several additional Jenkins-specific files that will need to be created for each indicator, as well as some configuration additions to the runtime host. It will be important to pair with a platform engineer to prepare the necessary production environment needs, test the workflow, validate on production, and ultimately sign off on a production release.
