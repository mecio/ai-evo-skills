# Example: delayed background job

This file demonstrates structure only. Replace it with evidence verified against the adopting project.

## Symptoms

A background operation has a stable identifier but remains pending beyond its documented service window.

## First safe check

Confirm, through the project's read-only observability interface, whether an enqueue event exists for the exact
job identifier and record its timestamp. Do not retry, cancel or mutate the job during classification.

Expected result: either one enqueue event is found, which justifies inspecting worker progress, or no enqueue
event exists, which redirects the investigation to the producing application.

## Recovery

Project-specific and intentionally omitted from this portable example.
