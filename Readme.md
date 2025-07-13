# Scoll video renderer API for the Podology app

This is a simple FastAPI server that expects a call from within a `Renderer` object in [Podology](https://github.com/andmbg/podology) containing a list of (timestamp, token) tuples representing the named entities identified in a transcript. It then prepares from it a video that is tailored to being displayed next to an episode transcript and synced to its scroll position. In its present form, named entities scroll horizontally through the image, but really there are no limits to how one might want to map scroll position in the transcript (think: user attention) to representation of named entities in the view.

## Getting started

Once cloned to the host system,

1. create `.env`
2. build docker image
3. run

### 1. `.env`

This file is necessary for the API to run and it contains only one value:

    API_TOKEN=...

The `API_TOKEN` can be anything, and you will paste it also in the main Podology `.env`. This is to limit access to the API to your own app.

### 2. Build image

With `.env` in place, enter

    docker build -t renderer .

Wait for the image to build, then run it.

### 3. run

Run the docker image using

    docker run --gpus all -d --rm --name renderer -p 8002:8002 renderer

If you want to watch the API work by keeping a terminal open and watching log messages, use

    docker logs -f renderer

That should be it.
