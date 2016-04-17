#!/usr/bin/env python

"""
This python script generates the py_class_impl! macro.
"""

header = '''
// Copyright (c) 2016 Daniel Grunwald
//
// Permission is hereby granted, free of charge, to any person obtaining a copy of this
// software and associated documentation files (the "Software"), to deal in the Software
// without restriction, including without limitation the rights to use, copy, modify, merge,
// publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons
// to whom the Software is furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in all copies or
// substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
// INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
// PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
// FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
// OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
// DEALINGS IN THE SOFTWARE.
'''

macro_start = '''
#[macro_export]
#[doc(hidden)]
macro_rules! py_class_impl {
    // TT muncher macro. Results are accumulated in $info $slots $impls and $members.
'''

base_case = '''
    // Base case: we're done munching and can start producing code:
    { $class:ident $py:ident
        /* info: */ {
            $base_type:ty,
            $size:expr,
            $gc:tt,
            /* data: */ [ $( { $data_offset:expr, $data_name:ident, $data_ty:ty } )* ]
        }
        $slots:tt { $( $imp:item )* } $members:tt;
    } => {
        struct $class { _unsafe_inner: $crate::PyObject }

        pyobject_to_pyobject!($class);

        impl $crate::PythonObject for $class {
            #[inline]
            fn as_object(&self) -> &$crate::PyObject {
                &self._unsafe_inner
            }

            #[inline]
            fn into_object(self) -> $crate::PyObject {
                self._unsafe_inner
            }

            /// Unchecked downcast from PyObject to Self.
            /// Undefined behavior if the input object does not have the expected type.
            #[inline]
            unsafe fn unchecked_downcast_from(obj: $crate::PyObject) -> Self {
                $class { _unsafe_inner: obj }
            }

            /// Unchecked downcast from PyObject to Self.
            /// Undefined behavior if the input object does not have the expected type.
            #[inline]
            unsafe fn unchecked_downcast_borrow_from<'a>(obj: &'a $crate::PyObject) -> &'a Self {
                ::std::mem::transmute(obj)
            }
        }

        impl $crate::PythonObjectWithCheckedDowncast for $class {
            #[inline]
            fn downcast_from<'p>(py: $crate::Python<'p>, obj: $crate::PyObject) -> Result<$class, $crate::PythonObjectDowncastError<'p>> {
                if py.get_type::<$class>().is_instance(py, &obj) {
                    Ok($class { _unsafe_inner: obj })
                } else {
                    Err($crate::PythonObjectDowncastError(py))
                }
            }

            #[inline]
            fn downcast_borrow_from<'a, 'p>(py: $crate::Python<'p>, obj: &'a $crate::PyObject) -> Result<&'a $class, $crate::PythonObjectDowncastError<'p>> {
                if py.get_type::<$class>().is_instance(py, obj) {
                    unsafe { Ok(::std::mem::transmute(obj)) }
                } else {
                    Err($crate::PythonObjectDowncastError(py))
                }
            }
        }

        py_coerce_item! {
            impl $crate::py_class::BaseObject for $class {
                type InitType = ( $( $data_ty, )* );

                #[inline]
                fn size() -> usize {
                    $size
                }

                unsafe fn alloc(
                    py: $crate::Python,
                    ty: &$crate::PyType,
                    ( $( $data_name, )* ): Self::InitType
                ) -> $crate::PyResult<$crate::PyObject>
                {
                    let obj = try!(<$base_type as $crate::py_class::BaseObject>::alloc(py, ty, ()));
                    $( $crate::py_class::data_init::<$data_ty>(py, &obj, $data_offset, $data_name); )*
                    Ok(obj)
                }

                unsafe fn dealloc(py: $crate::Python, obj: *mut $crate::_detail::ffi::PyObject) {
                    $( $crate::py_class::data_drop::<$data_ty>(py, obj, $data_offset); )*
                    <$base_type as $crate::py_class::BaseObject>::dealloc(py, obj)
                }
            }
        }
        $($imp)*
        py_coerce_item! {
            impl $class {
                fn create_instance(py: $crate::Python $( , $data_name : $data_ty )* ) -> $crate::PyResult<$class> {
                    let obj = try!(unsafe {
                        <$class as $crate::py_class::BaseObject>::alloc(
                            py, &py.get_type::<$class>(), ( $($data_name,)* )
                        )
                    });
                    return Ok($class { _unsafe_inner: obj });

                    // hide statics in create_instance to avoid name conflicts
                    static mut type_object : $crate::_detail::ffi::PyTypeObject
                        = py_class_type_object_static_init!($class, $gc, $slots);
                    static mut init_active: bool = false;

                    // trait implementations that need direct access to type_object
                    impl $crate::PythonObjectWithTypeObject for $class {
                        fn type_object(py: $crate::Python) -> $crate::PyType {
                            unsafe {
                                if $crate::py_class::is_ready(py, &type_object) {
                                    $crate::PyType::from_type_ptr(py, &mut type_object)
                                } else {
                                    // automatically initialize the class on-demand
                                    <$class as $crate::py_class::PythonObjectFromPyClassMacro>::initialize(py)
                                        .expect(concat!("An error occurred while initializing class ", stringify!($class)))
                                }
                            }
                        }
                    }

                    impl $crate::py_class::PythonObjectFromPyClassMacro for $class {
                        fn initialize(py: $crate::Python) -> $crate::PyResult<$crate::PyType> {
                            unsafe {
                                if $crate::py_class::is_ready(py, &type_object) {
                                    return Ok($crate::PyType::from_type_ptr(py, &mut type_object));
                                }
                                assert!(!init_active,
                                    concat!("Reentrancy detected: already initializing class ",
                                    stringify!($class)));
                                init_active = true;
                                let res = init(py);
                                init_active = false;
                                res
                            }
                        }
                    }

                    fn init($py: $crate::Python) -> $crate::PyResult<$crate::PyType> {
                        py_class_type_object_dynamic_init!($class, $py, type_object);
                        py_class_init_members!($class, $py, type_object, $members);
                        unsafe {
                            if $crate::_detail::ffi::PyType_Ready(&mut type_object) == 0 {
                                Ok($crate::PyType::from_type_ptr($py, &mut type_object))
                            } else {
                                Err($crate::PyErr::fetch($py))
                            }
                        }
                    }
                }
            }
        }
    };
'''

def data_decl():
    print('''
    // Data declaration
    { $class:ident $py:ident
        /* info: */ {
            $base_type: ty,
            $size: expr,
            $gc: tt,
            [ $( $data:tt )* ]
        }
        $slots:tt { $( $imp:item )* } $members:tt;
        data $data_name:ident : $data_type:ty; $($tail:tt)*
    } => { py_class_impl! {
        $class $py
        /* info: */ {
            $base_type,
            /* size: */ $crate::py_class::data_new_size::<$data_type>($size),
            $gc,
            /* data: */ [
                $($data)*
                {
                    $crate::py_class::data_offset::<$data_type>($size),
                    $data_name,
                    $data_type
                }
            ]
        }
        $slots
        /* impl: */ {
            $($imp)*
            impl $class {
                fn $data_name<'a>(&'a self, py: $crate::Python<'a>) -> &'a $data_type {
                    unsafe {
                        $crate::py_class::data_get::<$data_type>(
                            py,
                            &self._unsafe_inner,
                            $crate::py_class::data_offset::<$data_type>($size)
                        )
                    }
                }
            }
        }
        $members;
        $($tail)*
    }};
''')

def tp_new(with_params):
    if with_params:
        param_capture = ', $($p:tt)+'
        tp_new = '''py_argparse_parse_plist_impl!{
                    py_class_wrap_newfunc {$class::__new__}
                    [] ($($p)+,)
                }'''
        impl = '''py_argparse_parse_plist_impl!{
                py_class_impl_item { $class, $py, __new__($cls: &$crate::PyType,) $res_type; { $($body)* } }
                [] ($($p)+,)
            }'''
        print('    // def __new__(cls, params)')
    else:
        param_capture = ''
        tp_new = 'py_class_wrap_newfunc!($class::__new__ [])'
        impl = 'py_class_impl_item! { $class, $py, __new__($cls: &$crate::PyType,) $res_type; { $($body)* } [] }'
        print('    // def __new__(cls)')
    print('''    { $class:ident $py:ident $info:tt
        /* slots: */ {
            /* type_slots */ [ $( $slot_name:ident : $slot_value:expr, )* ]
            $as_number:tt $as_sequence:tt
        }
        { $( $imp:item )* } $members:tt;
        def __new__ ($cls:ident%s)
            -> $res_type:ty { $( $body:tt )* } $($tail:tt)*
    } => { py_class_impl! {
        $class $py $info
        /* slots: */ {
            /* type_slots */ [
                $( $slot_name : $slot_value, )*
                tp_new: Some(%s),
            ]
            $as_number $as_sequence
        }
        /* impl: */ {
            $($imp)*
            %s
        }
        $members;
        $($tail)*
    }};''' % (param_capture, tp_new, impl))

def traverse_and_clear():
    print('''
    // def __traverse__(self, visit)
    { $class:ident $py:ident
        /* info: */ {
            $base_type: ty,
            $size: expr,
            /* gc: */ {
                /* traverse_proc: */ None,
                $traverse_data: tt
            },
            $datas: tt
        }
        $slots:tt { $( $imp:item )* } $members:tt;
        def __traverse__(&$slf:tt, $visit:ident) $body:block $($tail:tt)*
    } => { py_class_impl! {
        $class $py
        /* info: */ {
            $base_type,
            $size,
            /* gc: */ {
                /* traverse_proc: */ $class::__traverse__,
                $traverse_data
            },
            $datas
        }
        $slots
        /* impl: */ {
            $($imp)*
            py_coerce_item!{
                impl $class {
                    fn __traverse__(&$slf,
                        $py: $crate::Python,
                        $visit: $crate::py_class::gc::VisitProc)
                    -> Result<(), $crate::py_class::gc::TraverseError>
                    $body
                }
            }
        }
        $members; $($tail)*
    }};
    // def __clear__(&self)
    { $class:ident $py:ident $info:tt
        /* slots: */ {
            /* type_slots */ [ $( $slot_name:ident : $slot_value:expr, )* ]
            $as_number:tt $as_sequence:tt
        }
        { $( $imp:item )* } $members:tt;
        def __clear__ (&$slf:ident) $body:block $($tail:tt)*
    } => { py_class_impl! {
        $class $py $info
        /* slots: */ {
            /* type_slots */ [
                $( $slot_name : $slot_value, )*
                tp_clear: py_class_tp_clear!($class),
            ]
            $as_number $as_sequence
        }
        /* impl: */ {
            $($imp)*
            py_coerce_item!{
                impl $class {
                    fn __clear__(&$slf, $py: $crate::Python) $body
                }
            }
        }
        $members;
        $($tail)*
    }};''')

general_cases = '''
    // def instance_method(&self)
    { $class:ident $py:ident $info:tt $slots:tt
        { $( $imp:item )* }
        { $( $member_name:ident = $member_expr:expr; )* };
        def $name:ident (&$slf:ident)
            -> $res_type:ty { $( $body:tt )* } $($tail:tt)*
    } => { py_class_impl! {
        $class $py $info $slots
        /* impl: */ {
            $($imp)*
            py_class_impl_item! { $class, $py, $name(&$slf,) $res_type; { $($body)* } [] }
        }
        /* members: */ {
            $( $member_name = $member_expr; )*
            $name = py_class_instance_method!{$py, $class::$name []};
        };
        $($tail)*
    }};
    // def instance_method(&self, params)
    { $class:ident $py:ident $info:tt $slots:tt
        { $( $imp:item )* }
        { $( $member_name:ident = $member_expr:expr; )* };
        def $name:ident (&$slf:ident, $($p:tt)+)
            -> $res_type:ty { $( $body:tt )* } $($tail:tt)*
    } => { py_class_impl! {
        $class $py $info $slots
        /* impl: */ {
            $($imp)*
            py_argparse_parse_plist_impl!{
                py_class_impl_item { $class, $py, $name(&$slf,) $res_type; { $($body)* } }
                [] ($($p)+,)
            }
        }
        /* members: */ {
            $( $member_name = $member_expr; )*
            $name = py_argparse_parse_plist_impl!{
                py_class_instance_method {$py, $class::$name}
                [] ($($p)+,)
            };
        };
        $($tail)*
    }};

    // @classmethod def class_method(cls)
    { $class:ident $py:ident $info:tt $slots:tt
        { $( $imp:item )* }
        { $( $member_name:ident = $member_expr:expr; )* };
        @classmethod def $name:ident ($cls:ident)
            -> $res_type:ty { $( $body:tt )* } $($tail:tt)*
    } => { py_class_impl! {
        $class $py $info $slots
        /* impl: */ {
            $($imp)*
            py_class_impl_item! { $class, $py, $name($cls: &$crate::PyType,) $res_type; { $($body)* } [] }
        }
        /* members: */ {
            $( $member_name = $member_expr; )*
            $name = py_class_class_method!{$py, $class::$name []};
        };
        $($tail)*
    }};
    // @classmethod def class_method(cls, params)
    { $class:ident $py:ident $info:tt $slots:tt
        { $( $imp:item )* }
        { $( $member_name:ident = $member_expr:expr; )* };
        @classmethod def $name:ident ($cls:ident, $($p:tt)+)
            -> $res_type:ty { $( $body:tt )* } $($tail:tt)*
    } => { py_class_impl! {
        $class $py $info $slots
        /* impl: */ {
            $($imp)*
            py_argparse_parse_plist_impl!{
                py_class_impl_item { $class, $py, $name($cls: &$crate::PyType,) $res_type; { $($body)* } }
                [] ($($p)+,)
            }
        }
        /* members: */ {
            $( $member_name = $member_expr; )*
            $name = py_argparse_parse_plist_impl!{
                py_class_class_method {$py, $class::$name}
                [] ($($p)+,)
            };
        };
        $($tail)*
    }};

    // @staticmethod def static_method(params)
    { $class:ident $py:ident $info:tt $slots:tt
        { $( $imp:item )* }
        { $( $member_name:ident = $member_expr:expr; )* };
        @staticmethod def $name:ident ($($p:tt)*)
            -> $res_type:ty { $( $body:tt )* } $($tail:tt)*
    } => { py_class_impl! {
        $class $py $info $slots
        /* impl: */ {
            $($imp)*
            py_argparse_parse_plist!{
                py_class_impl_item { $class, $py, $name() $res_type; { $($body)* } }
                ($($p)*)
            }
        }
        /* members: */ {
            $( $member_name = $member_expr; )*
            $name = py_argparse_parse_plist!{
                py_class_static_method {$py, $class::$name}
                ($($p)*)
            };
        };
        $($tail)*
    }};

    // static static_var = expr;
    { $class:ident $py:ident $info:tt $slots:tt $impls:tt
        { $( $member_name:ident = $member_expr:expr; )* };
        static $name:ident = $init:expr; $($tail:tt)*
    } => { py_class_impl! {
        $class $py $info $slots $impls
        /* members: */ {
            $( $member_name = $member_expr; )*
            $name = $init;
        };
        $($tail)*
    }};
'''

macro_end = '''
}
'''

def special_method(decorated_function):
    def wrap1(*args, **kwargs):
        def wrap2(special_name):
            return decorated_function(special_name, *args, **kwargs)
        return wrap2
    return wrap1

@special_method
def error(special_name, msg):
    print('''// def %s()
    { $class:ident $py:ident $info:tt $slots:tt $impls:tt $members:tt;
        def %s $($tail:tt)*
    } => {
        py_error! { "%s" }
    };''' % (special_name, special_name, msg))

@special_method
def unimplemented(special_name):
    return error('%s is not supported by py_class! yet.' % special_name)(special_name)

special_names = {
    '__init__': error('__init__ is not supported by py_class!; use __new__ instead.'),
    '__del__': error('__del__ is not supported by py_class!; Use a data member with a Drop impl instead.'),
    '__repr__': unimplemented(),
    '__str__': unimplemented(),
    '__unicode__': unimplemented(),
    '__bytes__': unimplemented(),
    '__format__': unimplemented(),
    # Comparison Operators
    '__lt__': unimplemented(),
    '__le__': unimplemented(),
    '__gt__': unimplemented(),
    '__ge__': unimplemented(),
    '__eq__': unimplemented(),
    '__ne__': unimplemented(),
    '__cmp__': unimplemented(),
    '__hash__': unimplemented(),
    '__nonzero__': error('__nonzero__ is not supported by py_class!; use the Python 3 spelling __bool__ instead.'),
    '__bool__': unimplemented(),
    # Customizing attribute access
    '__getattr__': unimplemented(),
    '__getattribute__': unimplemented(),
    '__setattr__': unimplemented(),
    '__delattr__': unimplemented(),
    '__dir__': unimplemented(),
    
    # Implementing Descriptors
    '__get__': unimplemented(),
    '__set__': unimplemented(),
    '__delete__': unimplemented(),

    # Customizing instance and subclass checks
    '__instancecheck__': unimplemented(),
    '__subclasscheck__': unimplemented(),

    # Emulating callable objects
    '__call__': unimplemented(),
    
    # Emulating container types
    '__len__': unimplemented(),
    '__length_hint__': unimplemented(),
    '__getitem__': unimplemented(),
    '__missing__': unimplemented(),
    '__setitem__': unimplemented(),
    '__delitem__': unimplemented(),
    '__iter__': unimplemented(),
    '__next__': unimplemented(),
    '__reversed__': unimplemented(),
    '__contains__': unimplemented(),
    
    # Emulating numeric types
    '__add__': unimplemented(),
    '__sub__': unimplemented(),
    '__mul__': unimplemented(),
    '__matmul__': unimplemented(),
    '__div__': unimplemented(),
    '__truediv__': unimplemented(),
    '__floordiv__': unimplemented(),
    '__mod__': unimplemented(),
    '__divmod__': unimplemented(),
    '__pow__': unimplemented(),
    '__lshift__': unimplemented(),
    '__rshift__': unimplemented(),
    '__and__': unimplemented(),
    '__xor__': unimplemented(),
    '__or__': unimplemented(),
    
    # Emulating numeric types - reflected
    '__radd__': unimplemented(),
    '__rsub__': unimplemented(),
    '__rmul__': unimplemented(),
    '__rmatmul__': unimplemented(),
    '__rdiv__': unimplemented(),
    '__rtruediv__': unimplemented(),
    '__rfloordiv__': unimplemented(),
    '__rmod__': unimplemented(),
    '__rdivmod__': unimplemented(),
    '__rpow__': unimplemented(),
    '__rlshift__': unimplemented(),
    '__rrshift__': unimplemented(),
    '__rand__': unimplemented(),
    '__rxor__': unimplemented(),
    '__ror__': unimplemented(),

    # Emulating numeric types - in-place
    '__iadd__': unimplemented(),
    '__isub__': unimplemented(),
    '__imul__': unimplemented(),
    '__imatmul__': unimplemented(),
    '__idiv__': unimplemented(),
    '__itruediv__': unimplemented(),
    '__ifloordiv__': unimplemented(),
    '__imod__': unimplemented(),
    '__idivmod__': unimplemented(),
    '__ipow__': unimplemented(),
    '__ilshift__': unimplemented(),
    '__irshift__': unimplemented(),
    '__iand__': unimplemented(),
    '__ixor__': unimplemented(),
    '__ior__': unimplemented(),

    # Unary arithmetic
    '__neg__': unimplemented(),
    '__pos__': unimplemented(),
    '__abs__': unimplemented(),
    '__invert__': unimplemented(),
    '__complex__': unimplemented(),
    '__int__': unimplemented(),
    '__long__': unimplemented(),
    '__float__': unimplemented(),
    '__round__': unimplemented(),
    '__index__': unimplemented(),
    '__coerce__': unimplemented(),

    # With statement context managers
    '__enter__': unimplemented(),
    '__exit__': unimplemented(),

    # Coroutines
    '__await__': unimplemented(),
    '__aiter__': unimplemented(),
    '__aenter__': unimplemented(),
    '__aexit__': unimplemented(),
}

def main():
    print(header)
    print('')
    print('// !!!!!!!!!!!!!!!!!!!!!!!!!!!')
    print('// THIS IS A GENERATED FILE !!')
    print('//       DO NOT MODIFY      !!')
    print('// !!!!!!!!!!!!!!!!!!!!!!!!!!!')
    print(macro_start)
    print(base_case)
    data_decl()
    tp_new(False)
    tp_new(True)
    traverse_and_clear()
    for name, f in sorted(special_names.items()):
        f(name)
    print(general_cases)
    print(macro_end)

if __name__ == '__main__':
    main()
