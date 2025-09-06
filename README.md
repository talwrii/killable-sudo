# Killable sudo
**@readwithai** - [X](https://x.com/readwithai) - [blog](https://readwithai.substack.com/) - [machine-aided reading](https://www.reddit.com/r/machineAidedReading/) - [📖](https://readwithai.substack.com/p/what-is-reading-broadly-defined
)[⚡️](https://readwithai.substack.com/s/technical-miscellany)[🖋️](https://readwithai.substack.com/p/note-taking-with-obsidian-much-of)

A wrapper around sudo which allows you to kill a process run with sudo as a normal user.

This is really intended for a [limited set of commands run as sudo without a password](https://unix.stackexchange.com/questions/215412/allow-certain-guests-to-execute-certain-commands) rather than 'full root" access - since a user with full root access via sudo can kill processes with `sudo kill`. My personal motivation was running processes started by a service manager not running as root.

It is also to be noted that similar effects can be achieved with [progress groups](https://www.andy-pearce.com/blog/posts/2013/Aug/process-groups-and-sessions/), which is the feature which allows `Ctrl-C` to kill process run with `sudo`. You can kill a process group by using kill with negative integers.

## Motivation
I was setting up a little router on a box which combines together a few services and a little glue. Naturally, as a router some of the things want to run as root,  but I didn't feel like running everything is a root. So I fell back to using sudo to provide access to a limited set of processes. `sudo` gives you nice fine-grained control over the commands that a user can run and is a nice alternative to setuid and can limit access to certain users so it seems a nice approach.

But I came across a problem: once you have started something with sudo you cannot kill it - or at least many server managers which use normal [signals](https://man7.org/linux/man-pages/man7/signal.7.html) to kill processes cannot.

As quick hack, I decided to vibe-code something which allows you to run a process with sudo and then kill it normally once you are done.

## How killable-sudo works
When you run a process with `killall-sudo` you create two shim processes. A user shim which exists to be killed with signals and tell the root shim, and a root shim that exists to kill the underlying process. When the user shim is killed it sends a message to the root shim via a fifo and that then kills the real process (and it's children).

`killable-sudo` will run this root shim process using `sudo`. So whatever user is using killable-sudo must be able run the root shim installed at `/opt/killable-sudo/killable-sudo` with sudo for examples [with a sudoers entry](https://toroid.org/sudoers-syntax) like this:

```
user ALL=(root) NOPASSWD: /opt/killable-sudo/killable-sudo
```

Of course, if your user has traditional password based sudo access, you could just type in your password rather than edit sudoers - but one of the use cases for `killable-sudo` is automated users which can run a limited set of processes as root.

This shim is running as root by the standard, so acts as an attack surface for privilege escalation. It was also written with some (slightly audited) vibe coding... which might not be the best of ideas! It is nevertheless a short, easily-revieawable section of Python code with no library dependencies (apart from Python itself - which isn't so short). Caveat emptor!

## Installation
First install the code using [pipx](https://github.com/pypa/pipx):

```
pipx install killable-sudo
```

You then need to install the root shim using `sudo killable-sudo --install` and give `sudo` the ability to run this shim as root for whatever user you are using. You can do this by adding the following entry to the sudoers file with `visudo`


```
user ALL=(root) NOPASSWD: /opt/killable-sudo/killable-sudo
```

## Usage
`killable-sudo` is run like like `sudo`, e.g.

```
killable-sudo top
```

This will spawn a tree of processes - which eventually runs `sudo top` as the user who executed this command. If you send kill signal to the top process then this entire tree will exit.

## About me
I am **@readwithai**. I create tools for reading, research and agency sometimes using the markdown editor [Obsidian](https://readwithai.substack.com/p/what-exactly-is-obsidian).

I also create a [stream of tools](https://readwithai.substack.com/p/my-productivity-tools) that are related to carrying out my work. You may be interested in some of these tools.

I write about lots of things - including tools like this - on [X](https://x.com/readwithai).
My [blog](https://readwithai.substack.com/) is more about reading and research and agency.
