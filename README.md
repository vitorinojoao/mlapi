# Machine Learning API

A template of a secure Application Programming Interface for Machine Learning models.  
Copyright (c) 2024 João Vitorino  

## Overview

To deploy ML models in a web server and securely access their predictions,  
you can use this API template and improve it to better suit your needs.  

The `app.py` is the main Python file with the creation of a Flask application,  
the initialization of several blueprints, and the setup of the default routes.  

The template is divided into three folders:

- **mlapi** - the entire Python code of the API with useful comments (e.g., blueprints and objects).
- **resources** - the resources required for the API to work properly (e.g., models and encodings).
- **files** - supplementary files to help you interact with the API (e.g., commands and requests).

![Overview](https://raw.githubusercontent.com/vitorinojoao/mlapi/main/files/overview.png)

## Important Notes

&rarr; **The run.py CLI command starts a development server!**  
The `run.py` can be used for a development server and also as the entry point of a production server.  
You should check the commands in `CLIrun.txt`.  
For production, you should use HTTPS with a valid TLS certificate and Nginx or a similar proxy server.  

&rarr; **A daemon service automatically starts the server!**  
The `mlapidaemon.service` can be used to run the server at boot and automatically restart it.  
You should check the commands in `CLIdaemon.txt`.  
It has missing information that must be specified according to the characteristics of a system.  

&rarr; **An API is only as secure as its authorization scheme!**  
A JWT authorization scheme with RSA signatures is implemented, but it must be used properly.  
You should ensure that every route requires an `Authorization header` and validates the token.  
After a reset, each client can use long-lived refresh tokens to get new temporary access tokens.  

![Scheme](https://raw.githubusercontent.com/vitorinojoao/mlapi/main/files/scheme.png)

## Sample Code

&rarr; **How to preprocess the JSON body of a request?**  
A 2D input array can be created, converting categorical features into numerical encodings.  
You can use and improve the code of `data_preprocessor.py`.  

&rarr; **How to load and use an ML model in an efficient way?**  
A model can be wrapped in a single object that is used to respond to every request.  
You can use and improve the code of `model_wrapper.py`.  

&rarr; **How to postprocess the anomaly or class predictions?**  
A 1D output array can be created, converting anomaly scores or confidence scores to labels.  
You can use and improve the code of `data_postprocessor.py`.  

&rarr; **How to send multiple requests to different routes?**  
Several GET and POST requests can be sent by each client, as long as they use valid tokens.  
You can see the possible requests in `mlapirequests.json`.  
