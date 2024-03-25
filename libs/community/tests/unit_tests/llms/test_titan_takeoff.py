"""Test Titan Takeoff LLM wrapper."""


import json

import pytest
import responses

from langchain_community.llms import TitanTakeoff, TitanTakeoffPro


@responses.activate
@pytest.mark.requires("takeoff_client")
@pytest.mark.parametrize("streaming", [True, False])
@pytest.mark.parametrize("takeoff_object", [TitanTakeoff, TitanTakeoffPro])
def test_titan_takeoff_call(streaming, takeoff_object) -> None:
    """Test valid call to Titan Takeoff."""
    port = 2345
    url = (
        f"http://localhost:{port}/generate_stream"
        if streaming
        else f"http://localhost:{port}/generate"
    )

    def stream_response(request):
        payload = json.loads(request.body)
        headers = {"request-id": "728d329e-0e86-11e4-a748-0c84dc037c13"}

        return (200, headers, json.dumps({"text": payload["text"]}))

    if streaming:
        responses.add_callback(responses.POST, url, callback=stream_response)
    else:
        responses.add(
            responses.POST,
            url,
            json={"text": "ask someone else"},
            content_type="application/json",
        )

    llm = takeoff_object(port=port, streaming=streaming)
    number_of_calls = 0
    for function_call in [llm, llm.invoke]:
        number_of_calls += 1
        output = function_call("What is 2 + 2?")
        assert isinstance(output, str)
        assert len(responses.calls) == number_of_calls
        assert responses.calls[0].request.url == url
        assert (
            json.loads(responses.calls[0].request.body.decode("utf-8"))["text"]
            == "What is 2 + 2?"
        )

    if streaming:
        output = llm._stream("What is 2 + 2?")
        for chunk in output:
            assert isinstance(chunk, str)
        assert len(responses.calls) == number_of_calls + 1
        assert responses.calls[0].request.url == url
        assert (
            json.loads(responses.calls[0].request.body.decode("utf-8"))["text"]
            == "What is 2 + 2?"
        )


@responses.activate
@pytest.mark.requires("takeoff_client")
@pytest.mark.parametrize("streaming", [True, False])
@pytest.mark.parametrize("takeoff_object", [TitanTakeoff, TitanTakeoffPro])
def test_titan_takeoff_bad_call(streaming, takeoff_object) -> None:
    """Test valid call to Titan Takeoff."""
    from takeoff_client import TakeoffError

    url = (
        "http://localhost:3000/generate"
        if not streaming
        else "http://localhost:3000/generate_stream"
    )
    responses.add(responses.POST, url, json={"text": "bad things"}, status=400)

    llm = takeoff_object(streaming=streaming)
    with pytest.raises(TakeoffError):
        llm("What is 2 + 2?")
    assert len(responses.calls) == 1
    assert responses.calls[0].request.url == url
    assert (
        json.loads(responses.calls[0].request.body.decode("utf-8"))["text"]
        == "What is 2 + 2?"
    )


@responses.activate
@pytest.mark.requires("takeoff_client")
@pytest.mark.parametrize("takeoff_object", [TitanTakeoff, TitanTakeoffPro])
def test_titan_takeoff_model_initialisation(takeoff_object) -> None:
    """Test valid call to Titan Takeoff."""
    mgnt_port = 36452
    inf_port = 46253
    mgnt_url = f"http://localhost:{mgnt_port}/reader"
    gen_url = f"http://localhost:{inf_port}/generate"
    reader_1 = {
        "model_name": "test",
        "device": "cpu",
        "consumer_group": "primary",
        "max_sequence_length": 512,
        "max_batch_size": 4,
        "tensor_parallel": 3,
    }
    reader_2 = reader_1.copy()
    reader_2["model_name"] = "test2"

    responses.add(responses.POST, mgnt_url, json={"key": "value"}, status=201)
    responses.add(responses.POST, gen_url, json={"text": "value"}, status=200)

    llm = takeoff_object(
        port=inf_port, mgmt_port=mgnt_port, models=[reader_1, reader_2]
    )
    output = llm("What is 2 + 2?")

    assert isinstance(output, str)
    # Ensure the management api was called to create the reader
    assert len(responses.calls) == 3
    for key, value in reader_1.items():
        assert json.loads(responses.calls[0].request.body.decode("utf-8"))[key] == value
    assert responses.calls[0].request.url == mgnt_url
    # Also second call should be made to spin uo reader 2
    for key, value in reader_2.items():
        assert json.loads(responses.calls[1].request.body.decode("utf-8"))[key] == value
    assert responses.calls[1].request.url == mgnt_url
    # Ensure the third call is to generate endpoint to inference
    assert responses.calls[2].request.url == gen_url
    assert (
        json.loads(responses.calls[2].request.body.decode("utf-8"))["text"]
        == "What is 2 + 2?"
    )