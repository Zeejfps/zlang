using LLVMSharp.Interop;
using ParserModule;
using ParserModule.Nodes;
using ParserModule.Visitors;

namespace CodeGenModule;

internal sealed class TypeVisitor : ITypeNodeVisitor
{
    public LLVMTypeRef Type { get; private set; }
    
    public void VisitNamedType(NamedTypeNode node)
    {
        Type = node.Identifier switch
        {
            "u64" or "i64" => LLVMTypeRef.Int64,
            "u32" or "i32" => LLVMTypeRef.Int32,
            "u16" or "i16" => LLVMTypeRef.Int16,
            "u8" or "i8" => LLVMTypeRef.Int8,
            "bool" => LLVMTypeRef.Int1,
            _ => throw new ArgumentOutOfRangeException()
        };
    }

    public void VisitPtrType(PtrTypeNode node)
    {
        if (node.GenericType == null)
        {
            Type = LLVMTypeRef.CreatePointer(LLVMTypeRef.Void, 0);
        }
        else
        {
            node.GenericType.Accept(this);
            var ptrType = Type;
            Type = LLVMTypeRef.CreatePointer(ptrType, 0);
        }
    }
}