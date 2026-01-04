# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

import torch
import torch.utils.benchmark as benchmark

import pytest


@pytest.mark.isaacsim_ci
def test_array_slicing():
    """Check that using ellipsis and slices work for torch tensors."""

    size = (400, 300, 5)
    my_tensor = torch.rand(size, device="cuda:0")

    assert my_tensor[..., 0].shape == (400, 300)
    assert my_tensor[:, :, 0].shape == (400, 300)
    assert my_tensor[slice(None), slice(None), 0].shape == (400, 300)
    with pytest.raises(IndexError):
        my_tensor[..., ..., 0]

    assert my_tensor[0, ...].shape == (300, 5)
    assert my_tensor[0, :, :].shape == (300, 5)
    assert my_tensor[0, slice(None), slice(None)].shape == (300, 5)
    assert my_tensor[0, ..., ...].shape == (300, 5)

    assert my_tensor[..., 0, 0].shape == (400,)
    assert my_tensor[slice(None), 0, 0].shape == (400,)
    assert my_tensor[:, 0, 0].shape == (400,)


@pytest.mark.isaacsim_ci
def test_array_circular():
    """Check circular buffer implementation in torch."""

    size = (10, 30, 5)
    my_tensor = torch.rand(size, device="cuda:0")

    # roll up the tensor without cloning
    my_tensor_1 = my_tensor.clone()
    my_tensor_1[:, 1:, :] = my_tensor_1[:, :-1, :]
    my_tensor_1[:, 0, :] = my_tensor[:, -1, :]
    # check that circular buffer works as expected
    error = torch.max(torch.abs(my_tensor_1 - my_tensor.roll(1, dims=1)))
    assert error.item() != 0.0
    assert not torch.allclose(my_tensor_1, my_tensor.roll(1, dims=1))

    # roll up the tensor with cloning
    my_tensor_2 = my_tensor.clone()
    my_tensor_2[:, 1:, :] = my_tensor_2[:, :-1, :].clone()
    my_tensor_2[:, 0, :] = my_tensor[:, -1, :]
    # check that circular buffer works as expected
    error = torch.max(torch.abs(my_tensor_2 - my_tensor.roll(1, dims=1)))
    assert error.item() == 0.0
    assert torch.allclose(my_tensor_2, my_tensor.roll(1, dims=1))

    # roll up the tensor with detach operation
    my_tensor_3 = my_tensor.clone()
    my_tensor_3[:, 1:, :] = my_tensor_3[:, :-1, :].detach()
    my_tensor_3[:, 0, :] = my_tensor[:, -1, :]
    # check that circular buffer works as expected
    error = torch.max(torch.abs(my_tensor_3 - my_tensor.roll(1, dims=1)))
    assert error.item() != 0.0
    assert not torch.allclose(my_tensor_3, my_tensor.roll(1, dims=1))

    # roll up the tensor with roll operation
    my_tensor_4 = my_tensor.clone()
    my_tensor_4 = my_tensor_4.roll(1, dims=1)
    my_tensor_4[:, 0, :] = my_tensor[:, -1, :]
    # check that circular buffer works as expected
    error = torch.max(torch.abs(my_tensor_4 - my_tensor.roll(1, dims=1)))
    assert error.item() == 0.0
    assert torch.allclose(my_tensor_4, my_tensor.roll(1, dims=1))


@pytest.mark.isaacsim_ci
def test_array_circular_copy():
    """Check that circular buffer implementation in torch is copying data."""

    size = (10, 30, 5)
    my_tensor = torch.rand(size, device="cuda:0")
    my_tensor_clone = my_tensor.clone()

    # roll up the tensor
    my_tensor_1 = my_tensor.clone()
    my_tensor_1[:, 1:, :] = my_tensor_1[:, :-1, :].clone()
    my_tensor_1[:, 0, :] = my_tensor[:, -1, :]
    # change the source tensor
    my_tensor[:, 0, :] = 1000
    # check that circular buffer works as expected
    assert not torch.allclose(my_tensor_1, my_tensor.roll(1, dims=1))
    assert torch.allclose(my_tensor_1, my_tensor_clone.roll(1, dims=1))


@pytest.mark.isaacsim_ci
def test_array_multi_indexing():
    """Check multi-indexing works for torch tensors."""

    size = (400, 300, 5)
    my_tensor = torch.rand(size, device="cuda:0")

    # this fails since array indexing cannot be broadcasted!!
    with pytest.raises(IndexError):
        my_tensor[[0, 1, 2, 3], [0, 1, 2, 3, 4]]


@pytest.mark.isaacsim_ci
def test_array_single_indexing():
    """Check how indexing effects the returned tensor."""

    size = (400, 300, 5)
    my_tensor = torch.rand(size, device="cuda:0")

    # obtain a slice of the tensor
    my_slice = my_tensor[0, ...]
    assert my_slice.untyped_storage().data_ptr() == my_tensor.untyped_storage().data_ptr()

    # obtain a slice over ranges
    my_slice = my_tensor[0:2, ...]
    assert my_slice.untyped_storage().data_ptr() == my_tensor.untyped_storage().data_ptr()

    # obtain a slice over list
    my_slice = my_tensor[[0, 1], ...]
    assert my_slice.untyped_storage().data_ptr() != my_tensor.untyped_storage().data_ptr()

    # obtain a slice over tensor
    my_slice = my_tensor[torch.tensor([0, 1]), ...]
    assert my_slice.untyped_storage().data_ptr() != my_tensor.untyped_storage().data_ptr()


@pytest.mark.isaacsim_ci
def test_logical_or():
    """Test bitwise or operation."""

    size = (400, 300, 5)
    my_tensor_1 = torch.rand(size, device="cuda:0") > 0.5
    my_tensor_2 = torch.rand(size, device="cuda:0") < 0.5

    # check the speed of logical or
    timer_logical_or = benchmark.Timer(
        stmt="torch.logical_or(my_tensor_1, my_tensor_2)",
        globals={"my_tensor_1": my_tensor_1, "my_tensor_2": my_tensor_2},
    )
    timer_bitwise_or = benchmark.Timer(
        stmt="my_tensor_1 | my_tensor_2", globals={"my_tensor_1": my_tensor_1, "my_tensor_2": my_tensor_2}
    )

    print("Time for logical or:", timer_logical_or.timeit(number=1000))
    print("Time for bitwise or:", timer_bitwise_or.timeit(number=1000))
    # check that logical or works as expected
    output_logical_or = torch.logical_or(my_tensor_1, my_tensor_2)
    output_bitwise_or = my_tensor_1 | my_tensor_2

    assert torch.allclose(output_logical_or, output_bitwise_or)


@pytest.mark.isaacsim_ci
def test_multi_array_indexing_vs_index_put():
    """Compare multiple methods for batched tensor indexing and assignment.

    This test benchmarks 9 different approaches for assigning values to non-contiguous indices.
    **All timings include index preparation overhead** to reflect realistic runtime scenarios where
    indices change frequently.

    1. **Fancy/Advanced Indexing** (tensor[idx0[:, None], idx1] = values)
       - Most Pythonic and readable
       - Minimal index preparation (just unsqueeze)
       - Directly supported by PyTorch
       - Good GPU performance for most cases

    2. **index_put_** (tensor.index_put_((idx0[:, None], idx1), values))
       - Explicit API for advanced indexing
       - Same index preparation as fancy indexing
       - Can specify accumulation mode (useful for duplicates)
       - Similar performance to fancy indexing

    3. **Strided Indexing** (tensor[idx0][:, idx1] = values)
       - WARNING: Creates intermediate copy, may not assign correctly
       - Minimal overhead but incorrect results
       - Shown for comparison but often incorrect
       - Slower due to extra memory operations

    4. **Meshgrid + Flatten** (compute meshgrid, flatten, then index)
       - Explicit index expansion via meshgrid
       - **Includes meshgrid computation in timing**
       - More memory overhead from intermediate tensors
       - Can be slow due to meshgrid cost

    5. **Linear Indexing** (convert 2D indices → 1D flat indices)
       - **Includes 2D→1D conversion in timing**
       - Reduces to simple 1D indexing
       - Can be very fast despite conversion overhead
       - Best for regular grid patterns

    6. **scatter_** (tensor.scatter_(dim, index, src))
       - Alternative PyTorch API
       - **Includes complex index preparation in timing**
       - Supports accumulation (add, multiply, etc.)
       - Most verbose index preparation
    """
    # define the shapes of the tensor and values
    tensor_shape = (4096, 18, 3)
    values_shape = (100, 12, 3)

    # create the tensor and values
    tensor = torch.rand(tensor_shape, device="cuda:0")
    values = torch.rand(values_shape, device="cuda:0")

    # Prepare indices (ensure unique indices to avoid duplicate assignments)
    idx0 = torch.randperm(tensor_shape[0], device="cuda:0")[: values_shape[0]]
    idx1 = torch.randperm(tensor_shape[1], device="cuda:0")[: values_shape[1]]

    print("\n" + "=" * 80)
    print("BENCHMARKING TENSOR INDEXING METHODS (including index preparation)")
    print("=" * 80)
    print(f"Tensor shape: {tensor_shape}, Values shape: {values_shape}")
    print(f"Indices: {len(idx0)} x {len(idx1)} = {len(idx0) * len(idx1)} assignments")
    print("=" * 80)

    # --- Method 1: Multi-array/fancy indexing (baseline)
    tensor1 = tensor.clone()
    timer_fancy = benchmark.Timer(
        stmt="t1[i0[:, None], i1] = vals",
        globals={"t1": tensor1, "i0": idx0, "i1": idx1, "vals": values},
    )
    fancy_result_time = timer_fancy.timeit(100)
    print(f"1. Fancy indexing:           {fancy_result_time.mean * 1000:.4f} ms")

    # --- Method 2: index_put_ (with index preparation)
    tensor2 = tensor.clone()
    timer_iput = benchmark.Timer(
        stmt="t2.index_put_((i0[:, None], i1), vals, accumulate=False)",
        globals={"t2": tensor2, "i0": idx0, "i1": idx1, "vals": values},
    )
    iput_result_time = timer_iput.timeit(100)
    print(f"2. index_put_:               {iput_result_time.mean * 1000:.4f} ms")

    # --- Method 3: strided indexing (WARNING: may not be equivalent!)
    tensor3 = tensor.clone()
    timer_strided = benchmark.Timer(
        stmt="t3[i0, :][:, i1] = vals",
        globals={"t3": tensor3, "i0": idx0, "i1": idx1, "vals": values},
    )
    strided_result_time = timer_strided.timeit(100)
    print(f"3. Strided indexing:         {strided_result_time.mean * 1000:.4f} ms (may be incorrect)")

    # --- Method 4: Meshgrid + flatten (including meshgrid computation)
    tensor4 = tensor.clone()
    timer_meshgrid = benchmark.Timer(
        stmt="""
ii_grid, jj_grid = torch.meshgrid(i0, i1, indexing="ij")
ii_flat = ii_grid.reshape(-1)
jj_flat = jj_grid.reshape(-1)
vals_flat = vals.reshape(-1, vals.shape[-1])
t4[ii_flat, jj_flat] = vals_flat
""",
        globals={"t4": tensor4, "i0": idx0, "i1": idx1, "vals": values, "torch": torch},
    )
    meshgrid_result_time = timer_meshgrid.timeit(100)
    print(f"4. Meshgrid + flatten:       {meshgrid_result_time.mean * 1000:.4f} ms (includes meshgrid)")

    # --- Method 5: Linear indexing (including linear index computation)
    tensor5 = tensor.clone()
    timer_linear = benchmark.Timer(
        stmt="""
linear_idx = (i0[:, None] * width + i1).reshape(-1)
vals_flat = vals.reshape(-1, vals.shape[-1])
t5_flat = t5.view(-1, vals.shape[-1])
t5_flat[linear_idx] = vals_flat
""",
        globals={"t5": tensor5, "i0": idx0, "i1": idx1, "vals": values, "width": tensor_shape[1]},
    )
    linear_result_time = timer_linear.timeit(100)
    print(f"5. Linear indexing:          {linear_result_time.mean * 1000:.4f} ms (includes conversion)")

    # --- Method 6: scatter_ (including index preparation)
    tensor6 = tensor.clone()
    timer_scatter = benchmark.Timer(
        stmt="""
idx_scatter = (i0[:, None].expand(-1, len(i1)) * width + i1).reshape(-1, 1).expand(-1, last_dim)
vals_flat = vals.reshape(-1, vals.shape[-1])
t6_2d = t6.view(-1, vals.shape[-1])
t6_2d.scatter_(0, idx_scatter, vals_flat)
""",
        globals={"t6": tensor6, "i0": idx0, "i1": idx1, "vals": values, "width": tensor_shape[1], "last_dim": tensor_shape[-1]},
    )
    scatter_result_time = timer_scatter.timeit(100)
    print(f"6. scatter_:                 {scatter_result_time.mean * 1000:.4f} ms (includes index prep)")

    # Actually perform the assignments on fresh clones (so correctness is checked independently)
    tensor1 = tensor.clone()
    tensor1[idx0[:, None], idx1] = values

    tensor2 = tensor.clone()
    tensor2.index_put_((idx0[:, None], idx1), values)

    tensor3 = tensor.clone()
    tensor3[idx0, :][:, idx1] = values

    # Recompute for method 4
    ii_grid, jj_grid = torch.meshgrid(idx0, idx1, indexing="ij")
    ii_flat = ii_grid.reshape(-1)
    jj_flat = jj_grid.reshape(-1)
    vals_flat = values.reshape(-1, values_shape[-1])

    tensor4 = tensor.clone()
    tensor4[ii_flat, jj_flat] = vals_flat

    # Recompute for method 5
    linear_idx = (idx0[:, None] * tensor_shape[1] + idx1).reshape(-1)
    tensor5 = tensor.clone()
    tensor5_flat = tensor5.view(-1, tensor_shape[-1])
    tensor5_flat[linear_idx] = vals_flat

    # Recompute for method 6
    idx_for_scatter = (idx0[:, None].expand(-1, len(idx1)) * tensor_shape[1] + idx1).reshape(-1, 1).expand(-1, tensor_shape[-1])
    tensor6 = tensor.clone()
    tensor6_2d = tensor6.view(-1, tensor_shape[-1])
    tensor6_2d.scatter_(0, idx_for_scatter, vals_flat)

    # Compare all methods
    print("\nCORRECTNESS VALIDATION:")
    print("-" * 80)
    try:
        torch.testing.assert_close(tensor1, tensor2, atol=1e-6, rtol=1e-5)
        print("✓ Method 1 (fancy) == Method 2 (index_put_)")
    except AssertionError as e:
        print(f"✗ Method 1 vs Method 2: {e}")

    try:
        torch.testing.assert_close(tensor1, tensor3, atol=1e-6, rtol=1e-5)
        print("✓ Method 1 (fancy) == Method 3 (strided)")
    except AssertionError:
        print("✗ Method 1 vs Method 3: MISMATCH (expected - strided indexing may copy)")

    try:
        torch.testing.assert_close(tensor1, tensor4, atol=1e-6, rtol=1e-5)
        print("✓ Method 1 (fancy) == Method 4 (meshgrid)")
    except AssertionError as e:
        print(f"✗ Method 1 vs Method 4: {e}")

    try:
        torch.testing.assert_close(tensor1, tensor5, atol=1e-6, rtol=1e-5)
        print("✓ Method 1 (fancy) == Method 5 (linear)")
    except AssertionError as e:
        print(f"✗ Method 1 vs Method 5: {e}")

    try:
        torch.testing.assert_close(tensor1, tensor6, atol=1e-6, rtol=1e-5)
        print("✓ Method 1 (fancy) == Method 6 (scatter_)")
    except AssertionError as e:
        print(f"✗ Method 1 vs Method 6: {e}")

    print("=" * 80)
