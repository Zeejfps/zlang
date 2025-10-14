using LLVMSharp.Interop;
using ParserModule;
using ParserModule.Nodes;

namespace CodeGenModule;

internal sealed class TypeVisitor : ITypeNodeVisitor
{
    public LLVMTypeRef Type { get; private set; }
    
    public void VisitNamedType(NamedTypeNode node)
    {
        Type = node.Name switch
        {
            "u32" or "i32" => LLVMTypeRef.Int32,
            "u8" or "i8" => LLVMTypeRef.Int8,
            _ => throw new ArgumentOutOfRangeException()
        };
    }
}