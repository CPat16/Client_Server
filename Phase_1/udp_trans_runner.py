# This file runs the server and client processes as threads
#   so that they may be run from single call

# Library imports
import threading
# Local imports
import udp_client
import udp_server


try:
  # create thread objects
  server_thread = threading.Thread(target=udp_server.server)
  client_thread = threading.Thread(target=udp_client.client)

  # start the server and client processes
  server_thread.start()
  client_thread.start()

  # wait for both threads to finish
  server_thread.join()
  client_thread.join()

  print("Finished transmission, closing...")

except:
  print("EXCEPTION: Exiting...")