# Copyright (c) 2015 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from unittest import mock

from oslo_serialization import jsonutils

from sahara.plugins import exceptions as p_exc
from sahara_plugin_ambari.plugins.ambari import client as ambari_client
from sahara_plugin_ambari.tests.unit import base


class AmbariClientTestCase(base.SaharaTestCase):
    def setUp(self):
        super(AmbariClientTestCase, self).setUp()

        self.http_client = mock.Mock()
        self.http_client.get = mock.Mock()
        self.http_client.post = mock.Mock()
        self.http_client.put = mock.Mock()
        self.http_client.delete = mock.Mock()

        self.headers = {"X-Requested-By": "sahara"}

        self.remote = mock.Mock()
        self.remote.get_http_client.return_value = self.http_client

        self.instance = mock.Mock()
        self.instance.remote.return_value = self.remote
        self.instance.management_ip = "1.2.3.4"

        self.good_pending_resp = mock.MagicMock()
        self.good_pending_resp.status_code = 200
        self.good_pending_resp.text = ('{"Requests": '
                                       '{"id": 1, "status": "PENDING"}}')

    def test_init_client_default(self):
        client = ambari_client.AmbariClient(self.instance)
        self.assertEqual(self.http_client, client._http_client)
        self.assertEqual("http://1.2.3.4:8080/api/v1", client._base_url)
        self.assertEqual("admin", client._auth.username)
        self.assertEqual("admin", client._auth.password)
        self.remote.get_http_client.assert_called_with("8080")

    def test_init_client_manual(self):
        client = ambari_client.AmbariClient(self.instance, port="1234",
                                            username="user", password="pass")
        self.assertEqual("http://1.2.3.4:1234/api/v1", client._base_url)
        self.assertEqual("user", client._auth.username)
        self.assertEqual("pass", client._auth.password)
        self.remote.get_http_client.assert_called_with("1234")

    def test_close_http_session(self):
        with ambari_client.AmbariClient(self.instance):
            pass
        self.remote.close_http_session.assert_called_with("8080")

    def test_get_method(self):
        client = ambari_client.AmbariClient(self.instance)
        client.get("http://spam")
        self.http_client.get.assert_called_with(
            "http://spam", verify=False, auth=client._auth,
            headers=self.headers)

    def test_post_method(self):
        client = ambari_client.AmbariClient(self.instance)
        client.post("http://spam", data="data")
        self.http_client.post.assert_called_with(
            "http://spam", data="data", verify=False, auth=client._auth,
            headers=self.headers)

    def test_put_method(self):
        client = ambari_client.AmbariClient(self.instance)
        client.put("http://spam", data="data")
        self.http_client.put.assert_called_with(
            "http://spam", data="data", verify=False, auth=client._auth,
            headers=self.headers)

    def test_delete_method(self):
        client = ambari_client.AmbariClient(self.instance)
        client.delete("http://spam")
        self.http_client.delete.assert_called_with(
            "http://spam", verify=False, auth=client._auth,
            headers=self.headers)

    def test_import_credential(self):
        resp = mock.Mock()
        resp.text = ""
        resp.status_code = 200
        self.http_client.post.return_value = resp
        client = ambari_client.AmbariClient(self.instance)

        client.import_credential("test", alias="credential",
                                 data={"some": "data"})
        self.http_client.post.assert_called_once_with(
            "http://1.2.3.4:8080/api/v1/clusters/test/credentials/credential",
            verify=False, data=jsonutils.dumps({"some": "data"}),
            auth=client._auth, headers=self.headers)

    def test_get_credential(self):
        resp = mock.Mock()
        resp.text = ""
        resp.status_code = 200
        self.http_client.get.return_value = resp
        client = ambari_client.AmbariClient(self.instance)

        client.get_credential("test", alias="credential")
        self.http_client.get.assert_called_once_with(
            "http://1.2.3.4:8080/api/v1/clusters/test/credentials/credential",
            verify=False, auth=client._auth, headers=self.headers)

        resp.status_code = 404
        self.assertRaises(ambari_client.AmbariNotFound,
                          ambari_client.AmbariClient.check_response,
                          resp, True)

    @mock.patch("sahara_plugin_ambari.plugins.ambari.client."
                "AmbariClient.check_response")
    def test_get_alerts_data(self, mock_check_response):
        cluster = mock.Mock()
        cluster.name = "test_cluster"

        client = ambari_client.AmbariClient(self.instance)

        # check_response returning empty json
        mock_check_response.return_value = {}

        res = client.get_alerts_data(cluster)
        self.assertEqual(res, [])

        self.http_client.get.assert_called_once_with(
            "http://1.2.3.4:8080/api/v1/clusters/test_cluster/alerts?fields=*",
            verify=False, auth=client._auth,
            headers=self.headers)

        mock_check_response.assert_called_once()

        # check_response returning json with items as key
        mock_check_response.return_value = {'items': ['item1', 'item2']}

        res = client.get_alerts_data(cluster)
        self.assertEqual(res, ['item1', 'item2'])

        self.http_client.get.assert_called_with(
            "http://1.2.3.4:8080/api/v1/clusters/test_cluster/alerts?fields=*",
            verify=False, auth=client._auth,
            headers=self.headers)

        self.assertEqual(self.http_client.get.call_count, 2)
        self.assertEqual(mock_check_response.call_count, 2)

    def test_check_response(self):
        resp = mock.Mock()
        resp.status_code = 404

        self.assertRaises(ambari_client.AmbariNotFound,
                          ambari_client.AmbariClient.check_response,
                          resp, True)

        resp.status_code = 200
        resp.text = u'{"json": "example"}'
        resp.raise_for_status = mock.Mock()

        res = ambari_client.AmbariClient.check_response(resp)

        self.assertEqual(res, {"json": "example"})
        resp.raise_for_status.assert_called_once()

    def test_req_id(self):
        resp = mock.Mock()

        resp.text = None
        self.assertRaises(p_exc.HadoopProvisionError,
                          ambari_client.AmbariClient.req_id, resp)

        resp.text = u'{"text" : "example"}'
        self.assertRaises(p_exc.HadoopProvisionError,
                          ambari_client.AmbariClient.req_id, resp)

        resp.text = u'{"Requests": {"example" : "text"}}'
        self.assertRaises(p_exc.HadoopProvisionError,
                          ambari_client.AmbariClient.req_id, resp)

        resp.text = u'{"Requests" : {"id" : "test_id"}}'
        res = ambari_client.AmbariClient.req_id(resp)
        self.assertEqual(res, "test_id")

    def test_get_registered_hosts(self):
        client = ambari_client.AmbariClient(self.instance)
        resp_data = """{
          "href" : "http://1.2.3.4:8080/api/v1/hosts",
          "items" : [
            {
              "href" : "http://1.2.3.4:8080/api/v1/hosts/host1",
              "Hosts" : {
                "host_name" : "host1"
              }
            },
            {
              "href" : "http://1.2.3.4:8080/api/v1/hosts/host2",
              "Hosts" : {
                "host_name" : "host2"
              }
            },
            {
              "href" : "http://1.2.3.4:8080/api/v1/hosts/host3",
              "Hosts" : {
                "host_name" : "host3"
              }
            }
          ]
        }"""
        resp = mock.Mock()
        resp.text = resp_data
        resp.status_code = 200
        self.http_client.get.return_value = resp
        hosts = client.get_registered_hosts()
        self.http_client.get.assert_called_with(
            "http://1.2.3.4:8080/api/v1/hosts", verify=False,
            auth=client._auth, headers=self.headers)
        self.assertEqual(3, len(hosts))
        self.assertEqual("host1", hosts[0]["Hosts"]["host_name"])
        self.assertEqual("host2", hosts[1]["Hosts"]["host_name"])
        self.assertEqual("host3", hosts[2]["Hosts"]["host_name"])

    def test_update_user_password(self):
        client = ambari_client.AmbariClient(self.instance)
        resp = mock.Mock()
        resp.text = ""
        resp.status_code = 200
        self.http_client.put.return_value = resp
        client.update_user_password("bart", "old_pw", "new_pw")
        exp_req = jsonutils.dumps({
            "Users": {
                "old_password": "old_pw",
                "password": "new_pw"
            }
        })
        self.http_client.put.assert_called_with(
            "http://1.2.3.4:8080/api/v1/users/bart", data=exp_req,
            verify=False, auth=client._auth, headers=self.headers)

    def test_create_blueprint(self):
        client = ambari_client.AmbariClient(self.instance)
        resp = mock.Mock()
        resp.text = ""
        resp.status_code = 200
        self.http_client.post.return_value = resp
        client.create_blueprint("cluster_name", {"some": "data"})
        self.http_client.post.assert_called_with(
            "http://1.2.3.4:8080/api/v1/blueprints/cluster_name",
            data=jsonutils.dumps({"some": "data"}), verify=False,
            auth=client._auth, headers=self.headers)

    def test_create_cluster(self):
        client = ambari_client.AmbariClient(self.instance)
        resp = mock.Mock()
        resp.text = """{
            "Requests": {
                "id": 1,
                "status": "InProgress"
            }
        }"""
        resp.status_code = 200
        self.http_client.post.return_value = resp
        req_info = client.create_cluster("cluster_name", {"some": "data"})
        self.assertEqual(1, req_info["id"])
        self.http_client.post.assert_called_with(
            "http://1.2.3.4:8080/api/v1/clusters/cluster_name",
            data=jsonutils.dumps({"some": "data"}), verify=False,
            auth=client._auth, headers=self.headers)

    def test_add_host_to_cluster(self):
        client = ambari_client.AmbariClient(self.instance)
        resp = mock.Mock()
        resp.text = ""
        resp.status_code = 200
        self.http_client.post.return_value = resp

        instance = mock.MagicMock()
        instance.fqdn.return_value = "i1"
        instance.cluster.name = "cl"

        client.add_host_to_cluster(instance)
        self.http_client.post.assert_called_with(
            "http://1.2.3.4:8080/api/v1/clusters/cl/hosts/i1",
            verify=False, auth=client._auth, headers=self.headers)

    def test_start_process_on_host(self):
        client = ambari_client.AmbariClient(self.instance)
        self.http_client.put.return_value = self.good_pending_resp
        client.wait_ambari_request = mock.MagicMock()

        instance = mock.MagicMock()
        instance.fqdn.return_value = "i1"
        instance.cluster.name = "cl"

        client.start_service_on_host(instance, "HDFS", 'STATE')
        self.http_client.put.assert_called_with(
            "http://1.2.3.4:8080/api/v1/clusters/"
            "cl/hosts/i1/host_components/HDFS",
            data=jsonutils.dumps(
                {
                    "HostRoles": {"state": "STATE"},
                    "RequestInfo": {
                        "context": "Starting service HDFS, "
                                   "moving to state STATE"}
                }),
            verify=False, auth=client._auth, headers=self.headers)

    def test_stop_process_on_host(self):
        client = ambari_client.AmbariClient(self.instance)
        check_mock = mock.MagicMock()
        check_mock.status_code = 200
        check_mock.text = '{"HostRoles": {"state": "SOME_STATE"}}'
        self.http_client.get.return_value = check_mock
        self.http_client.put.return_value = self.good_pending_resp
        client.wait_ambari_request = mock.MagicMock()
        instance = mock.MagicMock()
        instance.fqdn.return_value = "i1"

        client.stop_process_on_host("cluster_name", instance, "p1")
        self.http_client.put.assert_called_with(
            "http://1.2.3.4:8080/api/v1/clusters/"
            "cluster_name/hosts/i1/host_components/p1",
            data=jsonutils.dumps(
                {
                    "HostRoles": {"state": "INSTALLED"},
                    "RequestInfo": {"context": "Stopping p1"}
                }),
            verify=False, auth=client._auth, headers=self.headers)

    @mock.patch("sahara_plugin_ambari.plugins.ambari.client.context")
    def test_wait_ambari_request(self, mock_context):
        client = ambari_client.AmbariClient(self.instance)
        check_mock = mock.MagicMock()
        d1 = {"request_context": "r1", "request_status": "PENDING",
              "progress_percent": 42}
        d2 = {"request_context": "r1", "request_status": "COMPLETED",
              "progress_percent": 100}
        check_mock.side_effect = [d1, d2]
        client.check_request_status = check_mock

        client.wait_ambari_request("id1", "c1")

        check_mock.assert_has_calls([mock.call("c1", "id1"),
                                     mock.call("c1", "id1")])

    @mock.patch("sahara_plugin_ambari.plugins.ambari.client.context")
    def test_wait_ambari_request_error(self, mock_context):
        client = ambari_client.AmbariClient(self.instance)
        check_mock = mock.MagicMock()
        d1 = {"request_context": "r1", "request_status": "ERROR",
              "progress_percent": 146}
        check_mock.return_value = d1
        client.check_request_status = check_mock

        self.assertRaises(p_exc.HadoopProvisionError,
                          client.wait_ambari_request, "id1", "c1")
